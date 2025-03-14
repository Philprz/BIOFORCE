from fastapi import FastAPI, HTTPException, Depends, Body, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
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
    allow_origins=["*"],  # En production, restreindre aux domaines autorisés
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

async def get_llm_response(messages: List[Dict[str, str]], context: str) -> str:
    """Obtient une réponse du LLM"""
    try:
        system_message = {
            "role": "system", 
            "content": f"""Tu es BioforceBot, l'assistant virtuel officiel de Bioforce, une organisation qui forme des professionnels de l'humanitaire.
            
Tu dois répondre aux questions des candidats de manière précise et sympathique. Aide-les à naviguer dans leur processus de candidature et réponds à leurs questions sur les formations.

Utilise les informations suivantes pour répondre:

{context}

Si tu ne connais pas la réponse, suggère de contacter directement l'équipe Bioforce et ne tente pas d'inventer.
Réponds toujours en français, de manière concise mais complète.
Si la question porte sur le paiement des frais de 60€/20000 CFA, encourage le candidat à finaliser son paiement en expliquant que c'est une étape nécessaire pour accéder à la sélection.
"""
        }
        
        api_messages = [system_message] + messages
        
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=api_messages,
            max_tokens=500,
            temperature=0.7,
        )
        
        return response.choices[0].message.content
    
    except Exception as e:
        logger.error(f"Erreur lors de l'appel au LLM: {str(e)}")
        raise

# Routes API
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Endpoint principal du chatbot"""
    try:
        # Récupérer la dernière question de l'utilisateur
        last_message = request.messages[-1].content
        
        # Rechercher des informations pertinentes
        search_results = []
        try:
            search_results = await search_knowledge_base(last_message)
        except Exception as e:
            logger.warning(f"Erreur lors de la recherche dans la base de connaissances: {str(e)}")
            # Continuer sans résultats de recherche si erreur (ex: collection inexistante)
        
        # Formater le contexte pour le LLM
        context = ""
        if search_results:
            context = await format_context_from_results(search_results)
        
        # Message système pour guider le chatbot
        system_message = {
            "role": "system", 
            "content": """Vous êtes l'assistant virtuel de Bioforce, une organisation humanitaire qui propose des formations.
                       Votre rôle est d'aider les candidats avec leur dossier de candidature et de répondre à leurs questions
                       sur les formations, le processus de sélection, et les modalités d'inscription.
                       Soyez concis, précis et avenant dans vos réponses. Si vous ne connaissez pas la réponse à une question,
                       proposez au candidat de contacter directement l'équipe Bioforce."""
        }
        
        # Préparer les messages pour le LLM
        messages = [system_message]
        messages.extend([{"role": msg.role, "content": msg.content} for msg in request.messages])
        
        # Si contexte disponible, l'ajouter
        if context:
            messages.append({
                "role": "system",
                "content": f"Informations supplémentaires pouvant être utiles pour répondre à la question: {context}"
            })
        
        # Obtenir la réponse du LLM
        llm_response = await get_llm_response(messages, context)
        
        # Préparer la réponse
        response = ChatResponse(
            message=ChatMessage(role="assistant", content=llm_response),
            context=request.context,
            references=[{
                "question": result.get("question", ""),
                "answer": result.get("answer", ""),
                "category": result.get("category", ""),
                "url": result.get("url", ""),
                "score": result.get("score", 0)
            } for result in search_results[:3]] if search_results else []  # Limiter à 3 références
        )
        
        return response
    
    except Exception as e:
        logger.error(f"Erreur lors du traitement de la requête: {str(e)}")
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