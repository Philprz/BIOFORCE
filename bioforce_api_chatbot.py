from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import List, Dict, Any
from datetime import datetime
import os
import json
import logging
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from dotenv import load_dotenv
import uvicorn

# Chargement des variables d'environnement
load_dotenv()

# Configuration du logging
logging.basicConfig(
    level=logging.DEBUG,  
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Variables d'API et configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
QDRANT_URL = os.getenv('QDRANT_URL')
QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')
COLLECTION_NAME = os.getenv('QDRANT_COLLECTION', 'BIOFORCE')

# Vérification des variables essentielles
if not QDRANT_URL:
    logger.error("Variable d'environnement QDRANT_URL non définie")
    raise ValueError("QDRANT_URL doit être défini dans les variables d'environnement")

if not QDRANT_API_KEY:
    logger.warning("Variable d'environnement QDRANT_API_KEY non définie")

if not OPENAI_API_KEY:
    logger.error("Variable d'environnement OPENAI_API_KEY non définie")
    raise ValueError("OPENAI_API_KEY doit être défini dans les variables d'environnement")

# Initialisation des clients
logger.info("Initialisation du client OpenAI avec API_KEY: %s...", OPENAI_API_KEY[:5] if OPENAI_API_KEY else "Non définie")
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

logger.info(f"Initialisation du client Qdrant avec URL: {QDRANT_URL}")
logger.info(f"Qdrant API_KEY présente: {'Oui' if QDRANT_API_KEY else 'Non'}")
qdrant_client = AsyncQdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

# Fonction pour initialiser la collection Qdrant
async def initialize_qdrant_collection():
    """Crée la collection bioforce_faq si elle n'existe pas déjà"""
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
            import traceback
            logger.error(f"Stack trace: {traceback.format_exc()}")
            # Essayer de diagnostiquer le problème
            try:
                import socket
                import requests
                # Tester la connectivité réseau de base
                logger.debug(f"Test de connexion réseau vers {QDRANT_URL}...")
                # Extraire le nom d'hôte de l'URL
                from urllib.parse import urlparse
                parsed_url = urlparse(QDRANT_URL)
                hostname = parsed_url.netloc.split(":")[0]
                port = parsed_url.port or (443 if parsed_url.scheme == 'https' else 80)
                
                # Test de socket
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(5)
                    result = sock.connect_ex((hostname, port))
                    if result == 0:
                        logger.info(f"Connexion réseau réussie vers {hostname}:{port}")
                    else:
                        logger.error(f"Échec de la connexion réseau vers {hostname}:{port}, code: {result}")
                    sock.close()
                except Exception as sock_err:
                    logger.error(f"Erreur lors du test de socket: {str(sock_err)}")
                
                # Test HTTP simple
                try:
                    response = requests.get(QDRANT_URL, timeout=5)
                    logger.info(f"Test HTTP réussi, code: {response.status_code}")
                except Exception as req_err:
                    logger.error(f"Erreur lors du test HTTP: {str(req_err)}")
            except Exception as diag_err:
                logger.error(f"Erreur lors du diagnostic: {str(diag_err)}")
            
            # Continuer avec les autres tests
            raise
        
        if COLLECTION_NAME not in collection_names:
            logger.info(f"Création de la collection {COLLECTION_NAME}")
            
            # Créer la collection avec la dimension d'embedding d'OpenAI (1536 pour ada-002)
            logger.debug("Création de la collection avec vecteurs de taille 1536 et distance Cosine")
            try:
                await qdrant_client.create_collection(
                    collection_name=COLLECTION_NAME,
                    vectors_config={
                        "size": 1536,
                        "distance": "Cosine"
                    }
                )
                logger.info(f"Collection {COLLECTION_NAME} créée avec succès")
            except Exception as e:
                logger.error(f"Erreur lors de la création de la collection: {str(e)}")
                logger.error(f"Type d'erreur: {type(e).__name__}")
                import traceback
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
                import traceback
                logger.error(f"Stack trace: {traceback.format_exc()}")
                # Ne pas faire échouer le démarrage
            
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation de Qdrant: {str(e)}")
        # Afficher plus d'informations pour le diagnostic
        logger.error(f"Détails de connexion - URL: {QDRANT_URL}, Collection: {COLLECTION_NAME}")
        logger.error(f"Type d'erreur: {type(e).__name__}")
        # Afficher la stack trace complète pour faciliter le débogage
        import traceback
        logger.error(f"Stack trace: {traceback.format_exc()}")
        # Ne pas faire échouer le démarrage de l'application
        pass

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

# Événement de démarrage pour initialiser la collection
@app.on_event("startup")
async def startup_event():
    logger.info("=== DÉMARRAGE DU CHATBOT BIOFORCE ===")
    logger.info(f"Version: 1.0.0, Environnement: {os.getenv('ENVIRONMENT', 'production')}")
    logger.info(f"URL Qdrant: {QDRANT_URL}")
    logger.info(f"Collection: {COLLECTION_NAME}")
    await initialize_qdrant_collection()
    logger.info("=== INITIALISATION TERMINÉE ===")

# Modèles de données
class ChatMessage(BaseModel):
    role: str = "user"
    content: str

class ChatRequest(BaseModel):
    user_id: str
    messages: List[ChatMessage]
    context: Dict[str, Any] = {}

class ChatResponse(BaseModel):
    message: ChatMessage
    context: Dict[str, Any] = {}
    references: List[Dict[str, Any]] = []

class SearchRequest(BaseModel):
    query: str
    limit: int = 5

class SearchResponse(BaseModel):
    results: List[Dict[str, Any]]

# Fonctions utilitaires
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
        import traceback
        logger.error(f"Stack trace: {traceback.format_exc()}")
        raise

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
            import traceback
            logger.error(f"Stack trace: {traceback.format_exc()}")
            # Si nous ne pouvons pas générer l'embedding, nous ne pouvons pas continuer
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
            import traceback
            logger.error(f"Stack trace: {traceback.format_exc()}")
            # Si la recherche échoue, retourner une liste vide
            return []
        
        # Formater les résultats
        results = []
        try:
            for scored_point in search_result:
                # Structure générique pour gérer différents formats de payload
                result_data = {
                    "score": scored_point.score,
                }
                
                # Ajouter les champs du payload en fonction de ce qui est disponible
                payload = scored_point.payload
                
                # Si c'est une FAQ
                if "question" in payload:
                    result_data["question"] = payload.get("question")
                    result_data["answer"] = payload.get("answer")
                
                # Si c'est un contenu de page
                if "title" in payload:
                    result_data["title"] = payload.get("title")
                    result_data["content"] = payload.get("content", "")
                
                # Champs génériques communs
                for field in ["category", "url", "source_url", "type", "language"]:
                    if field in payload:
                        result_data[field] = payload.get(field)
                
                results.append(result_data)
            
            logger.debug(f"Premier résultat score: {results[0]['score'] if results else 'aucun'}")
        except Exception as e:
            logger.error(f"Erreur lors du traitement des résultats: {str(e)}")
            logger.error(f"Type d'erreur: {type(e).__name__}")
            import traceback
            logger.error(f"Stack trace: {traceback.format_exc()}")
            # Si le traitement échoue, retourner une liste vide
            return []
            
        return results
    
    except Exception as e:
        logger.error(f"Erreur lors de la recherche: {str(e)}")
        logger.error(f"Détails: collection={COLLECTION_NAME}, query='{query}', type d'erreur={type(e).__name__}")
        import traceback
        logger.error(f"Stack trace: {traceback.format_exc()}")
        # En cas d'erreur, retourner une liste vide plutôt que de faire échouer l'appel
        return []

async def format_context_from_results(results: List[Dict[str, Any]]) -> str:
    """Formate les résultats de recherche en contexte pour le LLM"""
    context = "Informations pertinentes de la base de connaissances de Bioforce:\n\n"
    
    for i, result in enumerate(results):
        context += f"Référence {i+1}:\n"
        context += f"Question: {result.get('question', 'Non disponible')}\n"
        context += f"Réponse: {result.get('answer', 'Non disponible')}\n"
        context += f"Catégorie: {result.get('category', 'Non disponible')}\n\n"
    
    return context

async def get_llm_response(messages, context=""):
    """
    Obtient une réponse du modèle de langage OpenAI
    """
    try:
        system_message = {
            "role": "system", 
            "content": """Vous êtes l'assistant virtuel de Bioforce, une organisation humanitaire qui propose des formations.
                       Votre rôle est d'aider les candidats avec leur dossier de candidature et de répondre à leurs questions
                       sur les formations, le processus de sélection, et les modalités d'inscription.
                       Soyez concis, précis et avenant dans vos réponses. Si vous ne connaissez pas la réponse à une question,
                       proposez au candidat de contacter directement l'équipe Bioforce."""
        }
        
        # Convertir les objets de message en dictionnaires pour l'API OpenAI
        api_messages = [system_message]
        
        # S'assurer que les messages sont au bon format pour l'API OpenAI
        for msg in messages:
            api_messages.append({"role": msg.role, "content": msg.content})
        
        # Si contexte disponible, l'ajouter
        if context:
            api_messages.append({
                "role": "system",
                "content": f"Informations supplémentaires pouvant être utiles pour répondre à la question: {context}"
            })
        
        logger.info(f"Envoi de la requête au modèle LLM avec {len(api_messages)} messages")
        
        # Obtenir la réponse du LLM
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=api_messages,
            temperature=0.7,
            max_tokens=500
        )
        
        content = response.choices[0].message.content
        logger.info(f"Réponse reçue du LLM ({len(content)} caractères)")
        
        return content, []
    
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        logger.error(f"Erreur lors de l'appel au LLM: {error_type} - {error_msg}")
        
        # Message d'erreur personnalisé pour l'utilisateur
        fallback_message = "Désolé, j'ai rencontré un problème technique. "
        
        if "API key" in error_msg.lower():
            fallback_message += "Il semble y avoir un problème avec la clé API. Veuillez contacter le support."
        elif "rate limit" in error_msg.lower():
            fallback_message += "Nos services sont actuellement très sollicités. Veuillez réessayer dans quelques instants."
        elif "timeout" in error_msg.lower():
            fallback_message += "La connexion semble lente. Veuillez réessayer votre question."
        else:
            fallback_message += "Veuillez réessayer ou contacter l'équipe Bioforce si le problème persiste."
        
        return fallback_message, []

# Routes API
@app.get("/")
async def root():
    """Redirige la racine vers l'interface d'administration"""
    return RedirectResponse(url="/admin/index.html")

@app.get("/admin/status")
async def admin_status():
    """Vérifie l'état des services de manière détaillée"""
    try:
        # Détermination de l'état du serveur
        server_status = "ok"
        server_message = "Serveur en cours d'exécution"
        
        # Vérification de l'état du scraping (pas de service réel)
        scraping_status = "ready"
        scraping_message = "Prêt à exécuter"
        
        # Vérification de la connexion à Qdrant
        qdrant_status = "unknown"
        qdrant_message = "État inconnu"
        
        try:
            # Test simple à Qdrant
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
        
        return {
            "server_status": server_status,
            "server_message": server_message,
            "qdrant_status": qdrant_status,
            "qdrant_message": qdrant_message,
            "scraping_status": scraping_status,
            "scraping_message": scraping_message
        }
    except Exception as e:
        logger.error(f"Erreur de vérification du statut: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Point d'entrée principal pour le chat
    """
    try:
        # Récupérer les messages. Nous n'utilisons pas user_id et context_info pour l'instant
        # mais ils pourraient être utiles dans le futur pour la personnalisation
        messages = request.messages
        
        # Récupérer le dernier message utilisateur
        last_message = None
        for msg in reversed(messages):
            if msg.role == "user":
                last_message = msg.content
                break
        
        if not last_message:
            raise HTTPException(status_code=400, detail="Aucun message utilisateur trouvé")
        
        logger.info(f"Traitement de la requête chat: '{last_message[:50]}...' (tronqué)")
        
        # Obtenir le contexte pertinent depuis Qdrant
        context = ""
        qdrant_results = []
        
        try:
            logger.info("Recherche de contexte dans Qdrant...")
            qdrant_results = await search_knowledge_base(last_message)
            
            if qdrant_results:
                logger.info(f"Contexte trouvé: {len(qdrant_results)} résultats")
                context = await format_context_from_results(qdrant_results)
            else:
                logger.warning("Aucun résultat trouvé dans Qdrant")
        except Exception as e:
            logger.error(f"Erreur lors de la requête Qdrant: {str(e)}")
            logger.info("Poursuite du traitement sans contexte")
            # On continue sans contexte
        
        # Construire et envoyer la requête à OpenAI
        response_content, references = await get_llm_response(messages, context)
        
        # Formater les références à partir des résultats Qdrant
        formatted_references = []
        for result in qdrant_results:
            ref = {
                "score": result.get("score", 0),
                "source": result.get("source_url", result.get("url", "Non disponible"))
            }
            
            # Ajouter les informations disponibles
            if "question" in result:
                ref["question"] = result["question"]
                ref["answer"] = result.get("answer", "")
            
            if "title" in result:
                ref["title"] = result["title"]
            
            if "category" in result:
                ref["category"] = result["category"]
                
            formatted_references.append(ref)
        
        # Formater et renvoyer la réponse
        return {
            "message": {
                "role": "assistant",
                "content": response_content
            },
            "references": formatted_references
        }
    except Exception as e:
        logger.error(f"Erreur dans /chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """Endpoint de recherche dans la base de connaissances"""
    try:
        results = await search_knowledge_base(request.query, request.limit)
        return SearchResponse(results=results)
    
    except Exception as e:
        logger.error(f"Erreur lors de la recherche: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Vérifie l'état de l'API"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/debug")
async def debug_api(request: dict = Body(...)):
    """Endpoint de débogage pour tester les appels API sans logique métier"""
    try:
        # Affichage détaillé des informations reçues
        logger.info(f"Request data: {json.dumps(request, default=str)}")
        
        # Vérification de la connexion à OpenAI
        openai_status = "unknown"
        try:
            # Test simple à OpenAI
            response = await openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=10
            )
            openai_status = "connected"
            openai_response = response.choices[0].message.content
        except Exception as e:
            openai_status = f"error: {str(e)}"
            openai_response = None
        
        # Vérification de la connexion à Qdrant
        qdrant_status = "unknown"
        try:
            # Test simple à Qdrant
            collections = await qdrant_client.get_collections()
            qdrant_status = "connected"
            qdrant_response = collections.collections
        except Exception as e:
            qdrant_status = f"error: {str(e)}"
            qdrant_response = None
        
        return {
            "timestamp": datetime.now().isoformat(),
            "request_received": True,
            "openai_status": openai_status,
            "openai_response": openai_response,
            "qdrant_status": qdrant_status,
            "qdrant_response": qdrant_response
        }
    except Exception as e:
        logger.error(f"Erreur de débogage: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("bioforce_api_chatbot:app", host="0.0.0.0", port=8000, reload=True)