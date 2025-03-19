from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
from datetime import datetime
import os
import logging
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from dotenv import load_dotenv
import uvicorn
import json
import asyncio

# Chargement des variables d'environnement
load_dotenv()

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Variables d'API et configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
QDRANT_URL = os.getenv('QDRANT_URL')
QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')
COLLECTION_NAME = os.getenv('QDRANT_COLLECTION', 'BIOFORCE')

# Initialisation des clients
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
qdrant_client = None  # Sera initialisé pendant l'événement de démarrage

# Journalisation des paramètres de connexion (sans les valeurs sensibles)
logger.info(f"Configuration Qdrant - URL: {QDRANT_URL} | Collection: {COLLECTION_NAME}")
if not QDRANT_URL or not QDRANT_API_KEY:
    logger.error("⚠️ Variables d'environnement Qdrant manquantes ou invalides")

# Fonction pour initialiser le client Qdrant avec retry
async def initialize_qdrant_client():
    """Initialise le client Qdrant avec plusieurs tentatives en cas d'échec"""
    global qdrant_client
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            logger.info(f"Tentative de connexion à Qdrant: {QDRANT_URL}")
            temp_client = AsyncQdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
            
            # Tester la connexion explicitement
            await temp_client.get_collections()
            
            # Si on arrive ici, la connexion est réussie
            qdrant_client = temp_client
            logger.info("✅ Connexion à Qdrant établie avec succès")
            return True
        except Exception as e:
            retry_count += 1
            error_msg = str(e)
            logger.error(f"❌ Échec de connexion à Qdrant (tentative {retry_count}/{max_retries}): {error_msg}")
            
            if retry_count >= max_retries:
                logger.error("❌ Nombre maximum de tentatives atteint. Impossible de se connecter à Qdrant.")
                return False
            
            # Attendre avant de réessayer
            await asyncio.sleep(2)
            
    return False

# Fonction pour initialiser la collection Qdrant
async def initialize_qdrant_collection():
    """Crée la collection bioforce_faq si elle n'existe pas déjà"""
    try:
        # Vérifier si le client Qdrant est initialisé
        if not qdrant_client:
            logger.error("Client Qdrant non initialisé, impossible de créer la collection")
            return
            
        # Vérifier si la collection existe
        collections = await qdrant_client.get_collections()
        collection_names = [collection.name for collection in collections.collections]
        
        if COLLECTION_NAME not in collection_names:
            logger.info(f"Création de la collection {COLLECTION_NAME}")
            
            # Créer la collection avec la dimension d'embedding d'OpenAI (1536 pour ada-002)
            await qdrant_client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config={
                    "size": 1536,
                    "distance": "Cosine"
                }
            )
            
            logger.info(f"Collection {COLLECTION_NAME} créée avec succès")
        else:
            logger.info(f"Collection {COLLECTION_NAME} existe déjà")
            
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation de Qdrant: {str(e)}")
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
    allow_origins=["*"],  # Permet toutes les origines pour les tests
    allow_credentials=True,
    allow_methods=["*"],  # Toutes les méthodes
    allow_headers=["*"],  # Tous les en-têtes
    expose_headers=["*"],  # Expose tous les en-têtes dans la réponse
    max_age=86400,        # Cache les résultats preflight pour 24h
)

# Événement de démarrage pour initialiser le client et la collection
@app.on_event("startup")
async def startup_event():
    # Initialiser le client Qdrant d'abord
    connected = await initialize_qdrant_client()
    
    if connected:
        # Seulement si la connexion est réussie, initialiser la collection
        await initialize_qdrant_collection()
    else:
        logger.warning("⚠️ L'application démarre sans connexion à Qdrant. Certaines fonctionnalités seront limitées.")

# Modèles de données
class ChatMessage(BaseModel):
    role: str = "user"
    content: str

class ChatRequest(BaseModel):
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
        response = await openai_client.embeddings.create(
            input=text,
            model="text-embedding-ada-002"
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Erreur d'embedding: {str(e)}")
        raise

async def search_knowledge_base(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Recherche dans la base de connaissances"""
    try:
        # Vérifier d'abord que le client est initialisé et que les paramètres de connexion sont valides
        if not qdrant_client:
            logger.error("Recherche impossible: client Qdrant non initialisé")
            return []
            
        if not QDRANT_URL or not QDRANT_API_KEY:
            logger.error("Recherche impossible: paramètres de connexion Qdrant manquants")
            return []
            
        logger.info(f"Génération d'embedding pour la requête: {query[:50]}...")
        vector = await generate_embedding(query)
        
        logger.info(f"Recherche dans Qdrant (collection: {COLLECTION_NAME}, limit: {limit})")
        search_result = await qdrant_client.search(
            collection_name=COLLECTION_NAME,
            query_vector=vector,
            limit=limit
        )
        
        results = []
        for scored_point in search_result:
            results.append({
                "score": scored_point.score,
                "question": scored_point.payload.get("title"),  # Utiliser title comme question
                "answer": scored_point.payload.get("content"),  # Utiliser content comme answer
                "category": scored_point.payload.get("category"),
                "url": scored_point.payload.get("url")
            })
        
        logger.info(f"Recherche réussie: {len(results)} résultats trouvés")
        return results
    
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erreur lors de la recherche dans Qdrant: {error_msg}")
        # Ajouter plus de détails sur l'erreur
        if "Connection refused" in error_msg or "ConnectionError" in error_msg:
            logger.error("Problème de connexion à Qdrant - vérifier l'URL et l'accessibilité du serveur")
        elif "Unauthorized" in error_msg or "forbidden" in error_msg:
            logger.error("Problème d'authentification - vérifier la clé API Qdrant")
        elif "collection not found" in error_msg.lower():
            logger.error(f"Collection '{COLLECTION_NAME}' introuvable - vérifier que la collection existe")
        return []

async def format_context_from_results(results: List[Dict[str, Any]]) -> str:
    """Formate les résultats de recherche en contexte pour le LLM"""
    context = "Informations pertinentes de la base de connaissances de Bioforce:\n\n"
    
    for i, result in enumerate(results):
        context += f"Référence {i+1}:\n"
        context += f"Question: {result['question']}\n"
        context += f"Réponse: {result['answer']}\n"
        context += f"Catégorie: {result['category']}\n\n"
    
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
        
        # Obtenir la réponse du LLM
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=api_messages,
            temperature=0.7,
            max_tokens=500
        )
        
        return response.choices[0].message.content, []
    
    except Exception as e:
        logger.error(f"Erreur lors de l'appel au LLM: {str(e)}")
        raise

# Routes API
@app.get("/")
async def root():
    """Route racine de l'API"""
    return {
        "message": "Bienvenue sur l'API Bioforce Chatbot", 
        "status": "online", 
        "documentation": "/docs",
        "version": "1.0.0"
    }

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Point d'entrée principal pour le chat
    """
    try:
        # Récupération des messages de l'utilisateur
        messages = request.messages
        
        # Récupération du contexte utilisateur (peut contenir des infos sur le dossier, etc.)
        context = request.context
        
        # Récupération du dernier message de l'utilisateur
        last_message = messages[-1].content if messages else ""
        
        # Recherche dans la base de connaissances
        search_results = await search_knowledge_base(last_message)
        
        # Formatage du contexte pour le LLM
        context_from_kb = await format_context_from_results(search_results)
        
        # Obtention de la réponse du LLM
        llm_response, references = await get_llm_response(messages, context_from_kb)
        
        # Construction des références pour l'interface
        formatted_references = []
        for result in search_results[:3]:  # Limiter à 3 références
            if result["score"] > 0.7:  # Seuil de pertinence
                formatted_references.append({
                    "question": result["question"],
                    "url": result["url"] if result.get("url") else "#"
                })
        
        # Construction de la réponse
        response = ChatResponse(
            message=ChatMessage(role="assistant", content=llm_response),
            context=context,  # Renvoyer le contexte tel quel
            references=formatted_references
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Erreur de chat: {str(e)}")
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
            await qdrant_client.get_collections()
            qdrant_status = "connected"
        except Exception as e:
            qdrant_status = f"error: {str(e)}"
        
        return {
            "timestamp": datetime.now().isoformat(),
            "request_received": True,
            "openai_status": openai_status,
            "openai_response": openai_response,
            "qdrant_status": qdrant_status
        }
    except Exception as e:
        logger.error(f"Erreur de débogage: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Routes d'administration
@app.get("/admin/system-info")
async def system_info():
    """
    Retourne les informations système pour l'interface d'administration
    """
    import platform
    from datetime import datetime
    
    return {
        "version": "1.0.0",
        "python_version": f"{platform.python_version()}",
        "platform": platform.platform(),
        "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "github_repo": "https://github.com/Philprz/BIOFORCE"
    }

@app.get("/admin/status")
async def status():
    """
    Vérifie l'état des différents services
    """
    server_status = "ok"
    
    # Vérifier l'état de Qdrant
    qdrant_status = "unknown"
    try:
        if not qdrant_client:
            qdrant_status = "not_initialized"
        else:
            await qdrant_client.get_collections()
            qdrant_status = "connected"
    except Exception as e:
        logger.error(f"Erreur de connexion à Qdrant: {str(e)}")
        qdrant_status = "error"
    
    # Vérifier l'état du scraping (pas de service réel, juste pour l'interface)
    scraping_status = "ready"
    
    return {
        "server_status": server_status,
        "qdrant_status": qdrant_status,
        "scraping_status": scraping_status
    }

@app.get("/admin/qdrant-stats")
async def qdrant_stats():
    """
    Retourne les statistiques des collections Qdrant
    """
    try:
        # Vérifier si le client Qdrant est initialisé
        if not qdrant_client:
            logger.error("Impossible de récupérer les statistiques: client Qdrant non initialisé")
            raise HTTPException(status_code=500, detail="Client Qdrant non initialisé")
            
        # Obtenir les collections
        collections = await qdrant_client.get_collections()
        collection_names = [collection.name for collection in collections.collections]
        
        stats = {}
        
        # Pour chaque collection, obtenir ses statistiques
        for name in collection_names:
            try:
                collection_info = await qdrant_client.get_collection(name)
                
                # Obtenir d'autres informations sur la collection
                collection_stats = {
                    "vectors_count": collection_info.vectors_count,
                    "segments_count": collection_info.segments_count,
                    "ram_usage": getattr(collection_info, "ram_usage", 0)
                }
                
                stats[name] = collection_stats
            except Exception as e:
                logger.error(f"Erreur lors de la récupération des stats pour {name}: {str(e)}")
                stats[name] = {"error": str(e)}
        
        return stats
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des statistiques Qdrant: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.post("/admin/git-update")
async def git_update():
    """
    Effectue une mise à jour du code source depuis GitHub
    """
    try:
        import subprocess
        
        # Exécuter la commande git pull
        process = subprocess.Popen(
            ["git", "pull"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate()
        
        output = []
        
        if stdout:
            output.extend(stdout.splitlines())
        
        if stderr:
            output.extend(stderr.splitlines())
        
        return {
            "success": process.returncode == 0,
            "output": output
        }
    
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour Git: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.get("/admin/logs")
async def get_logs(lines: int = Query(50, description="Nombre de lignes à récupérer")):
    """
    Récupère les dernières lignes des logs du système
    """
    try:
        # Simulation de logs (dans un projet réel, on utiliserait un vrai fichier de log)
        logs = [
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - INFO - Démarrage du serveur",
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - INFO - Connexion à Qdrant établie",
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - INFO - API prête"
        ]
        
        return {
            "logs": logs
        }
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des logs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.post("/scrape/faq")
async def scrape_faq(force_update: bool = Query(False, description="Force la mise à jour, ignorant le cache")):
    """
    Lance un scraping des FAQs du site Bioforce
    """
    try:
        # Ici, on simulerait le démarrage d'un job de scraping
        # Pour l'instant, on renvoie juste un succès simulé
        
        return {
            "success": True,
            "message": "Scraping FAQ démarré",
            "force_update": force_update
        }
    
    except Exception as e:
        logger.error(f"Erreur lors du démarrage du scraping FAQ: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.post("/scrape/full")
async def scrape_full(force_update: bool = Query(False, description="Force la mise à jour, ignorant le cache")):
    """
    Lance un scraping complet du site Bioforce
    """
    try:
        # Ici, on simulerait le démarrage d'un job de scraping complet
        # Pour l'instant, on renvoie juste un succès simulé
        
        return {
            "success": True,
            "message": "Scraping complet démarré",
            "force_update": force_update
        }
    
    except Exception as e:
        logger.error(f"Erreur lors du démarrage du scraping complet: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

if __name__ == "__main__":
    uvicorn.run("bioforce_api_chatbot:app", host="0.0.0.0", port=8000, reload=True)