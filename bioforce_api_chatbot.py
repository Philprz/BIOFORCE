from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
import os
import logging
import traceback
import time
import hashlib
import asyncio
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
from dotenv import load_dotenv
from pathlib import Path

# Chargement des variables d'environnement
load_dotenv()

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Variables d'API et configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
QDRANT_URL = os.getenv('QDRANT_URL')
QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')
COLLECTION_NAME = os.getenv('QDRANT_COLLECTION', 'BIOFORCE')
OPENAI_ASSISTANT_ID = os.getenv('OPENAI_ASSISTANT_ID')
USE_OPENAI_ASSISTANT = os.getenv('USE_OPENAI_ASSISTANT', 'true').lower() == 'true'

# Validation des variables essentielles
if not QDRANT_URL:
    logger.error("Variable d'environnement QDRANT_URL non définie")
    raise ValueError("QDRANT_URL doit être défini dans les variables d'environnement")

if not OPENAI_API_KEY:
    logger.error("Variable d'environnement OPENAI_API_KEY non définie")
    raise ValueError("OPENAI_API_KEY doit être défini dans les variables d'environnement")

if USE_OPENAI_ASSISTANT and not OPENAI_ASSISTANT_ID:
    logger.warning("OPENAI_ASSISTANT_ID non défini, désactivation de l'assistant")
    USE_OPENAI_ASSISTANT = False

if not QDRANT_API_KEY:
    logger.warning("Variable d'environnement QDRANT_API_KEY non définie")

# Initialisation des clients
logger.info(f"Initialisation du client OpenAI avec API_KEY: {OPENAI_API_KEY[:5]}..." if OPENAI_API_KEY else "API_KEY non définie")
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

logger.info(f"Initialisation du client Qdrant avec URL: {QDRANT_URL}")
logger.info(f"Qdrant API_KEY présente: {'Oui' if QDRANT_API_KEY else 'Non'}")
qdrant_client = AsyncQdrantClient(
    url=QDRANT_URL,
    api_key=QDRANT_API_KEY,
    prefer_grpc=False
)

# Cache pour les réponses enrichies
enriched_responses_cache = {}
# Durée de validité du cache (24 heures)
CACHE_VALIDITY_PERIOD = 24 * 60 * 60

# Initialisation de l'application FastAPI
app = FastAPI(
    title="BioforceBot API",
    description="API pour le chatbot d'assistance aux candidats Bioforce",
    version="1.0.0"
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=86400,
)

# Configuration des dossiers statiques
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

try:
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    logger.info(f"Dossier statique configuré: {STATIC_DIR}")
except Exception as e:
    logger.warning(f"Erreur lors de la configuration du dossier statique: {str(e)}")

try:
    templates = Jinja2Templates(directory=TEMPLATES_DIR)
    logger.info(f"Dossier templates configuré: {TEMPLATES_DIR}")
except Exception as e:
    logger.warning(f"Erreur lors de la configuration des templates: {str(e)}")

# Classe pour les messages de chat
class ChatMessage(BaseModel):
    role: str = "user"
    content: str

# Classe pour les requêtes de chat
class ChatRequest(BaseModel):
    user_id: str
    messages: List[ChatMessage]
    context: Dict[str, Any] = {}

# Classe pour les réponses de chat
class ChatResponse(BaseModel):
    message: ChatMessage
    context: Dict[str, Any] = {}
    references: List[Dict[str, Any]] = []
    has_enrichment_pending: bool = False
    websocket_id: Optional[str] = None

# Gestionnaire de connexions WebSocket
websocket_connections = {}

# Fonction pour générer une clé de cache à partir d'un message
def generate_cache_key(message: str) -> str:
    """Génère une clé de cache à partir d'un message en utilisant un hash."""
    normalized_message = message.lower().strip()
    return hashlib.md5(normalized_message.encode('utf-8')).hexdigest()

# Fonction pour vérifier si deux messages sont similaires
def are_messages_similar(message1: str, message2: str, threshold: float = 0.8) -> bool:
    """Détermine si deux messages sont similaires en fonction d'un seuil."""
    words1 = set(message1.lower().split())
    words2 = set(message2.lower().split())
    if not words1 or not words2:
        return False
    common_words = words1.intersection(words2)
    similarity = len(common_words) / max(len(words1), len(words2))
    return similarity >= threshold

# Fonction pour trouver une réponse similaire dans le cache
def find_similar_cached_response(message: str) -> Optional[Dict[str, Any]]:
    """Recherche une réponse à une question similaire dans le cache."""
    now = time.time()

    exact_key = generate_cache_key(message)
    if exact_key in enriched_responses_cache:
        cache_entry = enriched_responses_cache[exact_key]
        if now - cache_entry["timestamp"] < CACHE_VALIDITY_PERIOD:
            return cache_entry

    for key, entry in enriched_responses_cache.items():
        if now - entry["timestamp"] < CACHE_VALIDITY_PERIOD:
            if are_messages_similar(message, entry["original_query"]):
                return entry

    return None

# Fonction pour ajouter une réponse au cache
def add_to_cache(message: str, rag_response: str, enriched_response: str):
    """Ajoute une réponse au cache."""
    key = generate_cache_key(message)
    enriched_responses_cache[key] = {
        "original_query": message,
        "rag_response": rag_response,
        "enriched_response": enriched_response,
        "timestamp": time.time()
    }

# Fonction pour initialiser la collection Qdrant
async def initialize_qdrant_collection():
    """Crée la collection BIOFORCE si elle n'existe pas déjà"""
    try:
        logger.info(f"Tentative de connexion à Qdrant: {QDRANT_URL}, collection: {COLLECTION_NAME}")

        # Vérifier si la collection existe
        logger.debug("Récupération de la liste des collections...")
        try:
            collections = await qdrant_client.get_collections()
            collection_names = [collection.name for collection in collections.collections]
            logger.info(f"Collections existantes: {collection_names}")
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des collections: {str(e)}")
            logger.error(f"Type d'erreur: {type(e).__name__}")
            logger.error(f"Stack trace: {traceback.format_exc()}")
            raise

        if COLLECTION_NAME not in collection_names:
            logger.info(f"Création de la collection {COLLECTION_NAME}")

            # Créer la collection avec la dimension d'embedding d'OpenAI (1536 pour ada-002)
            logger.debug("Création de la collection avec vecteurs de taille 1536 et distance Cosine")
            try:
                await qdrant_client.create_collection(
                    collection_name=COLLECTION_NAME,
                    vectors_config=models.VectorParams(
                        size=1536,
                        distance=models.Distance.COSINE
                    )
                )
                logger.info(f"Collection {COLLECTION_NAME} créée avec succès")
            except Exception as e:
                logger.error(f"Erreur lors de la création de la collection: {str(e)}")
                logger.error(f"Type d'erreur: {type(e).__name__}")
                logger.error(f"Stack trace: {traceback.format_exc()}")
                raise
        else:
            # Obtenir des informations sur la collection
            logger.debug(f"Récupération des informations sur la collection {COLLECTION_NAME}")
            try:
                collection_info = await qdrant_client.get_collection(collection_name=COLLECTION_NAME)
                count = await qdrant_client.count(collection_name=COLLECTION_NAME)

                logger.info(f"Collection {COLLECTION_NAME} existe déjà avec {count.count} points")
                logger.debug(f"Info collection: {collection_info}")
            except Exception as e:
                logger.error(f"Erreur lors de la récupération des informations sur la collection: {str(e)}")
                logger.error(f"Type d'erreur: {type(e).__name__}")
                logger.error(f"Stack trace: {traceback.format_exc()}")
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation de Qdrant: {str(e)}")
        logger.error(f"Détails de connexion - URL: {QDRANT_URL}, Collection: {COLLECTION_NAME}")
        logger.error(f"Type d'erreur: {type(e).__name__}")
        logger.error(f"Stack trace: {traceback.format_exc()}")

# Événement de démarrage pour initialiser la collection
@app.on_event("startup")
async def startup_event():
    logger.info("=== DÉMARRAGE DU CHATBOT BIOFORCE ===")
    logger.info(f"Version: 1.0.0, Environnement: {os.getenv('ENVIRONMENT', 'production')}")
    logger.info(f"URL Qdrant: {QDRANT_URL}")
    logger.info(f"Collection: {COLLECTION_NAME}")
    await initialize_qdrant_collection()
    logger.info("=== INITIALISATION TERMINÉE ===")

# Fonction pour générer un embedding
async def generate_embedding(text: str) -> List[float]:
    """Génère un embedding pour le texte donné"""
    try:
        logger.debug(f"Génération de l'embedding pour le texte: '{text[:50]}...'")
        response = await openai_client.embeddings.create(
            input=text,
            model="text-embedding-ada-002"
        )
        logger.debug(f"Embedding généré avec succès, taille: {len(response.data[0].embedding)}")
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Erreur d'embedding: {str(e)}")
        logger.error(f"Type d'erreur: {type(e).__name__}")
        logger.error(f"Stack trace: {traceback.format_exc()}")
        raise

# Fonction pour rechercher dans Qdrant
async def search_knowledge_base(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Recherche dans la base de connaissances"""
    try:
        logger.info(f"Recherche pour la requête: '{query}' dans la collection {COLLECTION_NAME}")

        # Générer l'embedding de la requête
        logger.debug("Génération de l'embedding pour la recherche...")
        try:
            vector = await generate_embedding(query)
            logger.info(f"Embedding généré avec succès (taille: {len(vector)})")
        except Exception as e:
            logger.error(f"Erreur lors de la génération de l'embedding: {str(e)}")
            logger.error(f"Type d'erreur: {type(e).__name__}")
            logger.error(f"Stack trace: {traceback.format_exc()}")
            raise

        # Effectuer la recherche
        logger.debug(f"Exécution de la recherche dans {COLLECTION_NAME} avec limite={limit}")
        try:
            search_result = await qdrant_client.search(
                collection_name=COLLECTION_NAME,
                query_vector=vector,
                limit=limit,
                with_payload=True
            )
            logger.info(f"Résultats trouvés: {len(search_result)}")
        except Exception as e:
            logger.error(f"Erreur lors de la recherche dans Qdrant: {str(e)}")
            logger.error(f"Type d'erreur: {type(e).__name__}")
            logger.error(f"Stack trace: {traceback.format_exc()}")
            return []

        # Formater les résultats
        results = []
        try:
            for scored_point in search_result:
                result_data = {
                    "score": scored_point.score,
                }

                payload = scored_point.payload

                if "question" in payload:
                    result_data["question"] = payload.get("question", "")
                    result_data["answer"] = payload.get("answer", payload.get("reponse", ""))
                if "title" in payload:
                    result_data["title"] = payload.get("title", "")
                    result_data["content"] = payload.get("content", "")

                for field in ["category", "url", "source_url", "type", "language"]:
                    if field in payload:
                        result_data[field] = payload.get(field)

                results.append(result_data)

            logger.debug(f"Premier résultat score: {results[0]['score'] if results else 'aucun'}")
        except Exception as e:
            logger.error(f"Erreur lors du traitement des résultats: {str(e)}")
            logger.error(f"Type d'erreur: {type(e).__name__}")
            logger.error(f"Stack trace: {traceback.format_exc()}")
            return []

        return results

    except Exception as e:
        logger.error(f"Erreur lors de la recherche: {str(e)}")
        logger.error(f"Détails: collection={COLLECTION_NAME}, query='{query}', type d'erreur={type(e).__name__}")
        logger.error(f"Stack trace: {traceback.format_exc()}")
        return []

# Fonction pour formater le contexte
async def format_context_from_results(results: List[Dict[str, Any]]) -> str:
    """Formate les résultats de recherche en contexte pour le LLM"""
    context = "Informations pertinentes de la base de connaissances de Bioforce:\n\n"

    for i, result in enumerate(results):
        context += f"Référence {i+1}:\n"

        if "question" in result:
            context += f"Question: {result.get('question', 'Non disponible')}\n"
            context += f"Réponse: {result.get('answer', 'Non disponible')}\n"
        elif "title" in result:
            context += f"Titre: {result.get('title', 'Non disponible')}\n"
            context += f"Contenu: {result.get('content', 'Non disponible')}\n"

        context += f"Catégorie: {result.get('category', 'Non disponible')}\n\n"

    return context

# Fonction pour obtenir une réponse rapide via RAG
async def get_rag_response(messages, context=""):
    """Génère une réponse rapide basée sur le RAG."""
    last_message = None
    for msg in reversed(messages):
        if msg.role == "user":
            last_message = msg.content
            break

    if not last_message:
        return "Je n'ai pas compris votre question. Pouvez-vous reformuler ?", []

    # Rechercher dans Qdrant pour obtenir le contexte pertinent
    qdrant_results = await search_knowledge_base(last_message)

    # Formater le contexte pour le LLM
    context_text = ""
    if qdrant_results:
        context_text = await format_context_from_results(qdrant_results)

    system_message = {
        "role": "system",
        "content": """Vous êtes l'assistant virtuel de Bioforce, une organisation humanitaire qui propose des formations.
                   Votre rôle est d'aider les candidats avec leur dossier de candidature et de répondre à leurs questions
                   sur les formations, le processus de sélection, et les modalités d'inscription.
                   Soyez concis, précis et avenant dans vos réponses. Si vous ne connaissez pas la réponse à une question,
                   proposez au candidat de contacter directement l'équipe Bioforce."""
    }

    api_messages = [system_message]

    for msg in messages:
        api_messages.append({"role": msg.role, "content": msg.content})

    if context_text:
        api_messages.append({
            "role": "system",
            "content": f"Informations supplémentaires pouvant être utiles pour répondre à la question: {context_text}"
        })

    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",  # Modèle plus léger pour une réponse rapide
            messages=api_messages,
            temperature=0.7,
            max_tokens=500
        )

        content = response.choices[0].message.content
        return content, qdrant_results
    except Exception as e:
        logger.error(f"Erreur lors de l'appel au LLM: {str(e)}")
        return "Je rencontre des difficultés techniques. Veuillez réessayer ou contacter l'équipe Bioforce.", []

# Fonction pour obtenir une réponse enrichie à partir de l'assistant OpenAI
async def get_enriched_response(messages, context=""):
    """Obtient une réponse enrichie à partir de l'assistant OpenAI."""
    try:
        # Récupérer le dernier message de l'utilisateur
        last_message = None
        for msg in reversed(messages):
            if isinstance(msg, dict):
                if msg.get("role") == "user":
                    last_message = msg.get("content")
                    break
            elif hasattr(msg, 'role') and msg.role == "user":
                last_message = msg.content
                break

        if not last_message:
            return "Je n'ai pas pu analyser votre question."

        # Vérifier d'abord le cache
        cached_response = find_similar_cached_response(last_message)
        if cached_response:
            return cached_response["enriched_response"]

        if not USE_OPENAI_ASSISTANT or not OPENAI_ASSISTANT_ID:
            logger.warning("Assistant OpenAI non configuré, utilisation du modèle standard")
            # Utiliser le modèle standard si l'assistant n'est pas configuré
            system_message = {
                "role": "system",
                "content": """Vous êtes l'assistant virtuel de Bioforce, une organisation qui forme des professionnels 
                           pour le secteur humanitaire. Fournissez des informations détaillées et précises sur les 
                           formations, le processus de candidature et les options de financement."""
            }

            api_messages = [system_message]
            for msg in messages:
                if isinstance(msg, dict):
                    api_messages.append(msg)
                else:
                    api_messages.append({"role": msg.role, "content": msg.content})

            if context:
                api_messages.append({
                    "role": "system",
                    "content": f"Informations supplémentaires: {context}"
                })

            response = await openai_client.chat.completions.create(
                model="gpt-4",  # Modèle plus complet pour une réponse enrichie
                messages=api_messages,
                temperature=0.5,
                max_tokens=800
            )

            return response.choices[0].message.content

        # Si rien dans le cache, interroger l'assistant OpenAI
        # Étape 1: Créer un thread
        thread = await openai_client.beta.threads.create()

        # Étape 2: Ajouter les messages au thread
        for msg in messages:
            if isinstance(msg, dict):
                await openai_client.beta.threads.messages.create(
                    thread_id=thread.id,
                    role=msg.get("role", "user"),
                    content=msg.get("content", "")
                )
            else:
                await openai_client.beta.threads.messages.create(
                    thread_id=thread.id,
                    role=msg.role,
                    content=msg.content
                )

        # Ajouter le contexte si disponible
        if context:
            await openai_client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=f"Informations supplémentaires: {context}"
            )

        # Étape 3: Lancer le traitement via l'assistant
        run = await openai_client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=OPENAI_ASSISTANT_ID
        )

        # Étape 4: Attendre la fin de l'exécution avec un délai maximum
        max_wait_time = 20  # 20 secondes maximum
        start_time = time.time()

        while True:
            run_status = await openai_client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )

            if run_status.status in ["completed", "failed", "cancelled"]:
                break

            # Vérifier si le délai d'attente est dépassé
            if time.time() - start_time > max_wait_time:
                logger.warning("Délai d'attente dépassé pour l'assistant OpenAI")
                await openai_client.beta.threads.runs.cancel(
                    thread_id=thread.id,
                    run_id=run.id
                )
                break

            await asyncio.sleep(1)

        # Étape 5: Lire la réponse
        assistant_response = "Je n'ai pas pu obtenir d'informations actualisées pour le moment."

        if run_status.status == "completed":
            assistant_messages = await openai_client.beta.threads.messages.list(thread_id=thread.id)

            # Obtenir la dernière réponse de l'assistant
            for message in assistant_messages.data:
                if message.role == "assistant":
                    assistant_response = message.content[0].text.value
                    break

        return assistant_response

    except Exception as e:
        logger.error(f"Erreur lors de l'enrichissement: {str(e)}")
        return "Je n'ai pas pu obtenir d'informations supplémentaires pour le moment."

# Fonction pour comparer les réponses et générer un complément
def generate_complement(rag_response, enriched_response):
    """Compare les réponses RAG et enrichie pour générer un complément si nécessaire."""
    # Extraire les phrases des deux réponses
    def extract_sentences(text):
        return [s.strip() for s in text.split('.') if s.strip()]

    rag_sentences = set(extract_sentences(rag_response.lower()))
    enriched_sentences = extract_sentences(enriched_response.lower())

    # Identifier les phrases uniques dans la réponse enrichie
    new_information = []
    for sentence in enriched_sentences:
        is_new = True
        for rag_sentence in rag_sentences:
            if are_messages_similar(sentence, rag_sentence, threshold=0.7):
                is_new = False
                break

        if is_new and len(sentence) > 20:  # Ignorer les phrases trop courtes
            new_information.append(sentence)

    # S'il y a de nouvelles informations, créer un complément
    if new_information:
        complement = "Voici des informations complémentaires basées sur les dernières actualités:\n\n"
        complement += ". ".join(new_information[:3])  # Limiter à 3 nouvelles phrases
        complement += "."
        return complement

    return None

# WebSocket endpoint
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await websocket.accept()
    websocket_connections[client_id] = websocket

    try:
        while True:
            # Maintenir la connexion ouverte
            await websocket.receive_text()
    except WebSocketDisconnect:
        if client_id in websocket_connections:
            del websocket_connections[client_id]

# Traitement de l'enrichissement en arrière-plan
async def process_enrichment(messages, rag_response, websocket_id, user_id):
    try:
        # Récupérer le dernier message de l'utilisateur
        last_message = None
        for msg in reversed(messages):
            if isinstance(msg, dict):
                if msg.get("role") == "user":
                    last_message = msg.get("content")
                    break
            elif hasattr(msg, 'role') and msg.role == "user":
                last_message = msg.content
                break

        if not last_message:
            return

        # Vérifier si une réponse similaire existe dans le cache
        cached_response = find_similar_cached_response(last_message)
        if cached_response and websocket_id in websocket_connections:
            await websocket_connections[websocket_id].send_json({
                "type": "enrichment",
                "content": cached_response["enriched_response"]
            })
            return

        # Obtenir une réponse enrichie
        enriched_response = await get_enriched_response(messages)

        # Ajouter au cache
        add_to_cache(last_message, rag_response, enriched_response)

        # Comparer les réponses pour générer un complément
        complement = generate_complement(rag_response, enriched_response)

        # Envoyer le complément via WebSocket si disponible
        if complement and websocket_id in websocket_connections:
            await websocket_connections[websocket_id].send_json({
                "type": "enrichment",
                "content": complement
            })
        # Envoyer également une notification "pas de nouvelles informations" si aucun complément
        elif websocket_id in websocket_connections:
            await websocket_connections[websocket_id].send_json({
                "type": "no_enrichment",
                "content": "Je n'ai pas trouvé d'informations complémentaires récentes sur ce sujet."
            })

    except Exception as e:
        logger.error(f"Erreur lors du traitement de l'enrichissement: {str(e)}")
        # Essayer d'envoyer une notification d'erreur
        if websocket_id in websocket_connections:
            try:
                await websocket_connections[websocket_id].send_json({
                    "type": "error",
                    "content": "Je n'ai pas pu obtenir d'informations complémentaires pour le moment."
                })
            except Exception as e:
                # Vous pouvez journaliser l'erreur pour en savoir plus
                print(f"Une erreur est survenue: {e}")

# Routes API
@app.get("/")
async def root():
    """Redirige la racine vers l'interface d'administration"""
    return RedirectResponse(url="/admin/")

@app.get("/admin/")
async def admin_index(request: Request):
    """Page d'accueil de l'interface d'administration"""
    try:
        admin_index_file = TEMPLATES_DIR / "admin" / "index.html"
        if admin_index_file.exists():
            return templates.TemplateResponse("admin/index.html", {"request": request})
        else:
            static_admin_index = STATIC_DIR / "admin" / "index.html"
            if static_admin_index.exists():
                return FileResponse(static_admin_index)
            else:
                html_content = """
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Bioforce Admin</title>
                    <meta charset="utf-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1">
                    <style>
                        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; }
                        h1 { color: #ef5d21; }
                        .container { max-width: 800px; margin: 0 auto; }
                        .card { background: #f9f9f9; border-radius: 5px; padding: 15px; margin-bottom: 15px; }
                        .error { color: red; }
                        .success { color: green; }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>Bioforce Admin</h1>
                        <div class="card">
                            <h2>Statut du Système</h2>
                            <p>API: <span class="success">En ligne</span></p>
                            <p>Qdrant: <span class="error">Vérification en cours...</span></p>
                            <p>OpenAI: <span class="error">Vérification en cours...</span></p>
                        </div>
                        <div class="card">
                            <h2>Actions</h2>
                            <p>Vérifier le statut: <a href="/admin/status">Status API</a></p>
                        </div>
                    </div>
                </body>
                </html>
                """
                return HTMLResponse(content=html_content)
    except Exception as e:
        logger.error(f"Erreur lors de l'affichage de la page d'admin: {str(e)}")
        return HTMLResponse(content=f"<html><body><h1>Erreur</h1><p>{str(e)}</p></body></html>")

@app.get("/admin/status")
async def admin_status():
    """Vérifie l'état des services de manière détaillée"""
    try:
        server_status = "ok"
        server_message = "Serveur en cours d'exécution"

        scraping_status = "ready"
        scraping_message = "Prêt à exécuter"

        qdrant_status = "unknown"
        qdrant_message = "État inconnu"

        try:
            collections = await qdrant_client.get_collections()
            collection_names = [c.name for c in collections.collections]

            if COLLECTION_NAME in collection_names:
                qdrant_status = "connected"
                qdrant_message = f"Collection {COLLECTION_NAME} accessible"
            else:
                qdrant_status = "warning"
                qdrant_message = f"Connexion établie, mais collection {COLLECTION_NAME} non trouvée"
        except Exception as e:
            logger.error(f"Erreur Qdrant: {str(e)}")
            qdrant_status = "error"
            qdrant_message = f"Erreur: {str(e)}"

        openai_status = "unknown"
        openai_message = "État inconnu"

        try:
            response = await openai_client.embeddings.create(
                input="Test de connexion",
                model="text-embedding-ada-002"
            )
            if len(response.data) > 0:
                openai_status = "connected"
                openai_message = "Connexion à OpenAI établie"
        except Exception as e:
            logger.error(f"Erreur OpenAI: {str(e)}")
            openai_status = "error"
            openai_message = f"Erreur: {str(e)}"

        return {
            "server_status": server_status,
            "server_message": server_message,
            "qdrant_status": qdrant_status,
            "qdrant_message": qdrant_message,
            "scraping_status": scraping_status,
            "scraping_message": scraping_message,
            "openai_status": openai_status,
            "openai_message": openai_message
        }
    except Exception as e:
        logger.error(f"Erreur de vérification du statut: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    """
    Point d'entrée principal pour le chat avec approche hybride
    """
    try:
        messages = request.messages

        # Génération d'un websocket_id unique pour cette session
        websocket_id = f"{request.user_id}_{int(time.time())}"

        # Phase 1 : Obtention rapide d'une réponse via RAG
        rag_content, references = await get_rag_response(messages)

        # Préparer la réponse initiale
        response = {
            "message": {
                "role": "assistant",
                "content": rag_content
            },
            "context": request.context,
            "references": [
                {
                    "source": ref.get("source_url", ref.get("url", "Non disponible")),
                    "title": ref.get("title", ref.get("question", "Information")),
                    "score": ref.get("score", 0)
                } for ref in references
            ],
            "has_enrichment_pending": True,
            "websocket_id": websocket_id
        }

        # Phase 2 : Lancer l'enrichissement en arrière-plan
        background_tasks.add_task(
            process_enrichment,
            messages,
            rag_content,
            websocket_id,
            request.user_id
        )

        return response

    except Exception as e:
        logger.error(f"Erreur dans /chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Vérifie l'état de l'API"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("bioforce_api_chatbot:app", host="0.0.0.0", port=8000, reload=True)