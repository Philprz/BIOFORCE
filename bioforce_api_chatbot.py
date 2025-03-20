# Imports standards
import os
import sys
import json
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path

# Modification du sys.path pour inclure le répertoire parent
# Ceci permet d'importer des modules internes sans spécifier le chemin complet
parent_dir = str(Path(__file__).parent)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Imports externes
# Ces imports proviennent de bibliothèques externes installées via pip
import uvicorn  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
from fastapi import FastAPI, HTTPException, Query, Body  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402
from openai import AsyncOpenAI  # noqa: E402

# Imports internes
# Ces imports proviennent de modules internes au projet
from bioforce_scraper.utils.qdrant_connector import QdrantConnector  # noqa: E402
from bioforce_scraper.utils.embedding_generator import generate_embeddings  # noqa: E402

# Chargement des variables d'environnement
load_dotenv()

# Configuration de l'API
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "BIOFORCE")
COLLECTION_NAME_ALL = os.getenv("QDRANT_COLLECTION_ALL", "BIOFORCE_ALL")

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

# Initialisation des clients
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)  # Sera initialisé pendant l'événement de démarrage
qdrant_connector = None  # Sera initialisé pendant l'événement de démarrage

# Journalisation des paramètres de connexion (sans les valeurs sensibles)
logger.info(f"Configuration Qdrant - URL: {QDRANT_URL} | Collection: {COLLECTION_NAME}")
if not QDRANT_URL or not QDRANT_API_KEY:
    logger.error("⚠️ Variables d'environnement Qdrant manquantes ou invalides")

# Fonction pour initialiser le client Qdrant avec retry
async def initialize_qdrant_client():
    """Initialise le client Qdrant avec plusieurs tentatives en cas d'échec"""
    global qdrant_connector
    
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            logger.info(f"Tentative de connexion à Qdrant: {QDRANT_URL}")
            qdrant_connector = QdrantConnector(url=QDRANT_URL, api_key=QDRANT_API_KEY, collection_name=COLLECTION_NAME)
            
            # Tester la connexion explicitement en s'assurant que la collection existe
            qdrant_connector.ensure_collection()
            
            # Si on arrive ici, la connexion est réussie
            logger.info("✅ Connexion à Qdrant établie avec succès")
            return True
        except Exception as e:
            retry_count += 1
            logger.error(f"Erreur de connexion à Qdrant (tentative {retry_count}/{max_retries}): {e}")
            
            if retry_count < max_retries:
                # Attendre avant de réessayer (backoff exponentiel)
                wait_time = 2 ** retry_count
                logger.info(f"Nouvelle tentative dans {wait_time} secondes...")
                await asyncio.sleep(wait_time)
            else:
                logger.error("Échec de la connexion à Qdrant après plusieurs tentatives")
                return False

# Fonction pour initialiser la collection Qdrant
async def initialize_qdrant_collection():
    """Initialise la collection Qdrant si elle n'existe pas encore"""
    try:
        # Vérifier si le client Qdrant est initialisé
        if not qdrant_connector:
            logger.error("Client Qdrant non initialisé, impossible de créer la collection")
            return
            
        # Vérifier si la collection existe déjà
        collections = qdrant_connector.client.get_collections()
        collection_names = [collection.name for collection in collections.collections]
        
        if COLLECTION_NAME not in collection_names:
            logger.info(f"Création de la collection {COLLECTION_NAME}...")
            
            # Créer la collection avec la dimension d'embedding d'OpenAI (1536 pour ada-002)
            qdrant_connector.client.create_collection(
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
        logger.error(f"Erreur lors de l'initialisation de la collection: {e}")

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

# Monter les fichiers statiques
app.mount("/demo", StaticFiles(directory="demo_interface", html=True), name="demo")
app.mount("/admin", StaticFiles(directory="bioforce-admin", html=True), name="admin")

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
        return await generate_embeddings([text])
    except Exception as e:
        logger.error(f"Erreur d'embedding: {str(e)}")
        raise

async def search_knowledge_base(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Recherche dans la base de connaissances Qdrant
    
    Args:
        query: La requête utilisateur
        limit: Nombre maximum de résultats à retourner
        
    Returns:
        Liste des résultats trouvés
    """
    try:
        logger.info(f"Recherche pour '{query}' (limite: {limit})")
        
        # Vérification que le client Qdrant est initialisé
        if not qdrant_connector:
            logger.error("Client Qdrant non initialisé")
            raise Exception("Base de connaissances non disponible")
        
        # Génération de l'embedding pour la requête
        vector = await generate_embedding(query)
        if not vector:
            logger.error("Échec de génération de l'embedding")
            return []
        
        # Log du modèle d'embedding utilisé pour débogage
        logger.info(f"Recherche avec le modèle d'embedding: {os.getenv('EMBEDDING_MODEL', 'text-embedding-ada-002')}")
        
        # Résultats combinés des deux collections
        all_results = []
        
        # Paramètres optimisés pour améliorer la pertinence
        search_limit = 30  # Augmenté pour avoir plus de choix avant filtrage
        min_score_threshold = 0.005  # Seuil minimal plus élevé pour la pertinence
        
        # Filtres de pertinence pour la langue
        filter_conditions = {
            "language": ["fr", "en", None]  # Inclure les documents sans langue spécifiée
        }
        
        # Recherche dans la collection principale (BIOFORCE - FAQ)
        try:
            logger.info(f"Recherche dans Qdrant (collection: {COLLECTION_NAME}, limit: {search_limit})")
            original_collection = qdrant_connector.collection_name
            qdrant_connector.collection_name = COLLECTION_NAME
            
            search_results_faq = qdrant_connector.search(
                query_vector=vector,
                limit=search_limit,
                filter_conditions=filter_conditions
            )
            
            # Log des scores pour débogage
            if search_results_faq:
                top_score = search_results_faq[0]["score"] if search_results_faq else 0
                logger.info(f"Top score dans {COLLECTION_NAME}: {top_score}")
                scores_log = [f"{i+1}: {r['score']:.6f}" for i, r in enumerate(search_results_faq[:5])]
                logger.info(f"Top 5 scores: {', '.join(scores_log)}")
            
            # Ajouter une source pour identifier la collection
            for result in search_results_faq:
                result["collection"] = COLLECTION_NAME
            
            all_results.extend(search_results_faq)
            logger.info(f"Trouvé {len(search_results_faq)} résultats dans {COLLECTION_NAME}")
        except Exception as e:
            logger.error(f"Erreur lors de la recherche dans {COLLECTION_NAME}: {str(e)}")
        
        # Recherche dans la collection secondaire (BIOFORCE_ALL - Site complet)
        try:
            logger.info(f"Recherche dans Qdrant (collection: {COLLECTION_NAME_ALL}, limit: {search_limit})")
            qdrant_connector.collection_name = COLLECTION_NAME_ALL
            
            search_results_all = qdrant_connector.search(
                query_vector=vector,
                limit=search_limit,
                filter_conditions=filter_conditions
            )
            
            # Log des scores pour débogage
            if search_results_all:
                top_score = search_results_all[0]["score"] if search_results_all else 0
                logger.info(f"Top score dans {COLLECTION_NAME_ALL}: {top_score}")
                scores_log = [f"{i+1}: {r['score']:.6f}" for i, r in enumerate(search_results_all[:5])]
                logger.info(f"Top 5 scores: {', '.join(scores_log)}")
            
            # Ajouter une source pour identifier la collection
            for result in search_results_all:
                result["collection"] = COLLECTION_NAME_ALL
            
            all_results.extend(search_results_all)
            logger.info(f"Trouvé {len(search_results_all)} résultats dans {COLLECTION_NAME_ALL}")
        except Exception as e:
            logger.error(f"Erreur lors de la recherche dans {COLLECTION_NAME_ALL}: {str(e)}")
        
        # Restaurer la collection d'origine
        qdrant_connector.collection_name = original_collection
        
        if not all_results:
            logger.warning("Aucun résultat trouvé dans les deux collections")
            return []
        
        # Dédupliquer les résultats par URL
        url_seen = set()
        unique_results = []
        
        for result in all_results:
            payload = result.get("payload", {})
            url = payload.get("url") or payload.get("source_url")
            
            # Si pas d'URL ou URL pas encore vue, ajout aux résultats uniques
            if not url or url not in url_seen:
                if url:
                    url_seen.add(url)
                unique_results.append(result)
        
        # Filtrer et trier les résultats par score
        filtered_results = [r for r in unique_results if r["score"] > min_score_threshold]  # Filtrer les scores trop faibles
        sorted_results = sorted(filtered_results, key=lambda x: x["score"], reverse=True)
        
        # Limiter au nombre demandé
        results = sorted_results[:limit]
        
        # Log des scores finaux
        if results:
            top_score = results[0]["score"] if results else 0
            logger.info(f"Score final maximal après filtrage: {top_score}")
            scores_log = [f"{i+1}: {r['score']:.6f}" for i, r in enumerate(results)]
            logger.info(f"Scores finaux: {', '.join(scores_log)}")
        
        # Transformer les résultats pour l'API
        formatted_results = []
        for result in results:
            payload = result.get("payload", {})
            collection = result.get("collection", "inconnue")
            
            formatted_results.append({
                "score": result["score"],
                "question": payload.get("title"),  # Utiliser title comme question
                "answer": payload.get("content"),  # Utiliser content comme answer
                "category": payload.get("category"),
                "url": payload.get("url") or payload.get("source_url"),
                "collection": collection  # Ajouter la source de la collection
            })
        
        logger.info(f"Recherche réussie: {len(results)} résultats trouvés après fusion et déduplication")
        return formatted_results
    
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erreur lors de la recherche dans Qdrant: {error_msg}")
        # Ajouter plus de détails sur l'erreur
        if "Connection refused" in error_msg or "ConnectionError" in error_msg:
            logger.error("Problème de connexion à Qdrant - vérifier l'URL et l'accessibilité du serveur")
        elif "Unauthorized" in error_msg or "forbidden" in error_msg:
            logger.error("Problème d'authentification - vérifier la clé API Qdrant")
        elif "collection not found" in error_msg.lower():
            logger.error("Collection introuvable - vérifier que les collections existent")
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

# Version v1 de l'API (pour assurer la compatibilité avec le frontend)
@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat_v1(request: ChatRequest):
    """
    Point d'entrée pour le chat (API v1) - pour compatibilité
    Redirige vers la fonction chat standard
    """
    return await chat(request)

@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """Endpoint de recherche dans la base de connaissances"""
    try:
        results = await search_knowledge_base(request.query, request.limit)
        return SearchResponse(results=results)
    
    except Exception as e:
        logger.error(f"Erreur lors de la recherche: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Version v1 de l'API de recherche pour compatibilité
@app.post("/api/v1/search", response_model=SearchResponse)
async def search_v1(request: SearchRequest):
    """
    Endpoint de recherche (API v1) - pour compatibilité
    Redirige vers la fonction search standard
    """
    return await search(request)

@app.get("/health")
async def health_check():
    """Vérifie l'état de l'API"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/api/health")
async def api_health_check():
    """Route de santé additionnelle pour compatibilité"""
    return await health_check()

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
            qdrant_connector.client.get_collections()
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
        if not qdrant_connector:
            qdrant_status = "not_initialized"
        else:
            qdrant_connector.client.get_collections()
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
        if not qdrant_connector:
            logger.error("Impossible de récupérer les statistiques: client Qdrant non initialisé")
            raise HTTPException(status_code=500, detail="Client Qdrant non initialisé")
            
        # Obtenir les collections
        collections = qdrant_connector.client.get_collections()
        collection_names = [collection.name for collection in collections.collections]
        
        stats = {}
        
        # Pour chaque collection, obtenir ses statistiques
        for name in collection_names:
            try:
                collection_info = qdrant_connector.client.get_collection(name)
                
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
    uvicorn.run("bioforce_api_chatbot:app", host=API_HOST, port=API_PORT, reload=True)