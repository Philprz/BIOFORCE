from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
from datetime import datetime
import os
import asyncio
import json
import logging
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from dotenv import load_dotenv
import uvicorn
import uuid

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
COLLECTION_NAME = "BIOFORCE"

# Initialisation des clients
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
qdrant_client = AsyncQdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

# Fonction pour initialiser la collection Qdrant
async def initialize_qdrant_collection():
    """Crée la collection bioforce_faq si elle n'existe pas déjà"""
    try:
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

# Événement de démarrage pour initialiser la collection
@app.on_event("startup")
async def startup_event():
    await initialize_qdrant_collection()

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
        vector = await generate_embedding(query)
        
        search_result = await qdrant_client.search(
            collection_name=COLLECTION_NAME,
            query_vector=vector,
            limit=limit
        )
        
        results = []
        for scored_point in search_result:
            results.append({
                "score": scored_point.score,
                "question": scored_point.payload.get("question"),
                "answer": scored_point.payload.get("answer"),
                "category": scored_point.payload.get("category"),
                "url": scored_point.payload.get("url")
            })
        
        return results
    
    except Exception as e:
        logger.error(f"Erreur lors de la recherche: {str(e)}")
        raise

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
async def redirect_to_admin():
    """Redirige la racine vers l'interface d'administration"""
    return RedirectResponse(url="/admin/index.html")

@app.get("/admin/status")
async def admin_status():
    """
    Vérifie l'état du serveur et des services connectés de manière détaillée
    """
    server_status = "running"
    server_message = "Serveur en cours d'exécution"
    
    # Initialiser les statuts par défaut
    qdrant_status = "unknown"
    qdrant_message = "État inconnu"
    
    try:
        # Vérifier si le client Qdrant est initialisé
        if qdrant_client is None:
            qdrant_status = "not_initialized"
            qdrant_message = "Client non initialisé. Vérifiez les variables d'environnement."
        else:
            # Vérifier la connexion à Qdrant
            try:
                collections = await qdrant_client.get_collections()
                
                # Vérifier si la collection existe
                collection_names = [c.name for c in collections.collections]
                if COLLECTION_NAME in collection_names:
                    qdrant_status = "connected"
                    qdrant_message = f"Connexion établie, collection {COLLECTION_NAME} disponible"
                else:
                    qdrant_status = "warning"
                    qdrant_message = f"Connexion établie, mais collection {COLLECTION_NAME} non trouvée"
            except Exception as e:
                qdrant_status = "error"
                qdrant_message = f"Erreur lors du test: {str(e)}"
    except Exception as e:
        logger.error(f"Erreur lors de la vérification du statut: {str(e)}")
        qdrant_status = "error"
        qdrant_message = f"Erreur interne: {str(e)}"
    
    # Vérifier l'état du scraping (pas de service réel, juste pour l'interface)
    scraping_status = "ready"
    scraping_message = "Prêt à exécuter"
    
    # Utiliser JSONResponse pour un meilleur contrôle des en-têtes et du cache
    return JSONResponse(content={
        "server_status": server_status,
        "server_message": server_message,
        "qdrant_status": qdrant_status,
        "qdrant_message": qdrant_message,
        "scraping_status": scraping_status,
        "scraping_message": scraping_message
    }, headers={"Cache-Control": "no-store"})

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Point d'entrée principal pour le chat
    """
    try:
        user_id = request.user_id
        messages = request.messages
        context_info = request.context
        
        # Récupérer le dernier message utilisateur
        last_message = None
        for msg in reversed(messages):
            if msg.role == "user":
                last_message = msg.content
                break
        
        if not last_message:
            raise HTTPException(status_code=400, detail="Aucun message utilisateur trouvé")
        
        # Obtenir le contexte pertinent depuis Qdrant
        context = ""
        try:
            qdrant_results = await search_knowledge_base(last_message)
            if qdrant_results:
                context = "\n\n".join([f"Q: {item.question}\nR: {item.answer}" for item in qdrant_results])
        except Exception as e:
            logger.error(f"Erreur lors de la requête Qdrant: {e}")
            # On continue sans contexte
        
        # Construire et envoyer la requête à OpenAI
        response_content, references = await get_llm_response(messages, context)
        
        # Formater et renvoyer la réponse
        return {
            "message": {
                "role": "assistant",
                "content": response_content
            },
            "references": references
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
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)