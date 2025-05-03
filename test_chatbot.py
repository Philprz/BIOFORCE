"""
Script de test pour vérifier le fonctionnement du chatbot
"""
import os
import asyncio
import json
import logging
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List, Dict, Any
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient

# Configuration du logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_chatbot")

# Chargement des variables d'environnement
load_dotenv('.env')

# Modèles pour le test
class ChatMessage(BaseModel):
    role: str = "user"
    content: str

class ChatRequest(BaseModel):
    user_id: str
    messages: List[ChatMessage]
    context: Dict[str, Any] = {}

# Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
QDRANT_URL = os.getenv('QDRANT_URL')
QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')
COLLECTION_NAME = os.getenv('QDRANT_COLLECTION', 'BIOFORCE')

# Vérification des variables d'environnement
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY est manquant dans les variables d'environnement")
if not QDRANT_URL:
    raise ValueError("QDRANT_URL est manquant dans les variables d'environnement")
if not QDRANT_API_KEY:
    raise ValueError("QDRANT_API_KEY est manquant dans les variables d'environnement")

# Initialisation des clients
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
qdrant_client = AsyncQdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

async def generate_embedding(text: str) -> List[float]:
    """Génère un embedding pour le texte donné"""
    try:
        response = await openai_client.embeddings.create(
            input=text,
            model="text-embedding-ada-002"
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error("Erreur lors de la génération de l'embedding: %s", str(e))
        raise

async def search_knowledge_base(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Recherche dans la base de connaissances"""
    try:
        logger.info("Génération de l'embedding pour: '%s'", query)
        vector = await generate_embedding(query)
        
        logger.info("Recherche dans Qdrant (collection: %s) avec vecteur de taille %d", 
                   COLLECTION_NAME, len(vector))
        search_result = await qdrant_client.search(
            collection_name=COLLECTION_NAME,
            query_vector=vector,
            limit=limit,
            with_payload=True
        )
        
        results = []
        for scored_point in search_result:
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
        
        return results
    
    except Exception as e:
        logger.error("Erreur lors de la recherche: %s", str(e))
        raise

async def get_llm_response(messages: List[ChatMessage], context: str = ""):
    """
    Obtient une réponse du modèle de langage OpenAI
    """
    try:
        system_message = {
            "role": "system", 
            "content": """Vous êtes l'assistant virtuel de Bioforce, une organisation humanitaire qui propose des formations.
                       Votre rôle est d'aider les candidats avec leur dossier de candidature et de répondre à leurs questions
                       sur les formations, le processus de sélection, et les modalités d'inscription.
                       Soyez concis, précis et avenant dans vos réponses."""
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
        
        logger.info("Envoi de la requête au modèle LLM avec %d messages", len(api_messages))
        
        # Obtenir la réponse du LLM
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=api_messages,
            temperature=0.7,
            max_tokens=500
        )
        
        content = response.choices[0].message.content
        logger.info("Réponse reçue du LLM (%d caractères)", len(content))
        
        return content, []
    
    except Exception as e:
        logger.error("Erreur lors de l'appel au LLM: %s", str(e))
        raise

async def format_context_from_results(results: List[Dict[str, Any]]) -> str:
    """Formate les résultats de recherche en contexte pour le LLM"""
    context = "Informations pertinentes de la base de connaissances de Bioforce:\n\n"
    
    for i, result in enumerate(results):
        context += f"Référence {i+1} (score: {result['score']:.4f}):\n"
        
        # Ajouter les champs spécifiques s'ils existent
        if "question" in result:
            context += f"Question: {result.get('question', 'Non disponible')}\n"
            context += f"Réponse: {result.get('answer', 'Non disponible')}\n"
        
        if "title" in result:
            context += f"Titre: {result.get('title', 'Non disponible')}\n"
            if "content" in result:
                content = result.get("content", "")
                if len(content) > 300:
                    content = content[:300] + "..."
                context += f"Contenu: {content}\n"
        
        if "category" in result:
            context += f"Catégorie: {result.get('category', 'Non disponible')}\n"
        
        if "url" in result:
            context += f"URL: {result.get('url', 'Non disponible')}\n"
        
        context += "\n"
    
    return context

async def test_qdrant_connection():
    """Teste la connexion à Qdrant et vérifie la collection"""
    try:
        # Vérifier que Qdrant répond
        logger.info("Test de connexion à Qdrant...")
        collections = await qdrant_client.get_collections()
        collection_names = [c.name for c in collections.collections]
        
        logger.info("Collections disponibles: %s", ", ".join(collection_names))
        
        if COLLECTION_NAME in collection_names:
            logger.info("La collection %s est disponible", COLLECTION_NAME)
            return True
        else:
            logger.warning("La collection %s n'existe pas!", COLLECTION_NAME)
            return False
    except Exception as e:
        logger.error("Erreur lors du test de connexion à Qdrant: %s", str(e))
        return False

async def process_chat_request():
    user_query = "Combien de temps faut-il pour recevoir une réponse après avoir soumis ma candidature ?"
    
    logger.info("--- TEST DE CHATBOT ---")
    logger.info("Requête: %s", user_query)
    
    try:
        # 0. Vérifier la connexion à Qdrant
        await test_qdrant_connection()
        
        # 1. Recherche dans la base de connaissances
        logger.info("1. Recherche dans la base de connaissances...")
        search_results = await search_knowledge_base(user_query)
        
        logger.info("Résultats trouvés: %d", len(search_results))
        
        # 2. Formater le contexte
        logger.info("2. Formatage du contexte...")
        context = await format_context_from_results(search_results)
        
        # 3. Créer la requête
        messages = [ChatMessage(role="user", content=user_query)]
        
        # 4. Obtenir la réponse du LLM
        logger.info("3. Appel au LLM...")
        response_text, references = await get_llm_response(messages, context)
        
        logger.info("--- RÉPONSE FINALE ---")
        logger.info(response_text)
        
        return {
            "status": "success",
            "message": response_text,
            "results_count": len(search_results)
        }
        
    except Exception as e:
        logger.error("ERREUR: %s", str(e))
        return {
            "status": "error",
            "message": str(e)
        }

# Exécuter le test
if __name__ == "__main__":
    print("Démarrage du test du chatbot...")
    print(f"URL Qdrant: {QDRANT_URL}")
    print(f"Collection: {COLLECTION_NAME}")
    
    result = asyncio.run(process_chat_request())
    
    print("\n--- RÉSULTAT FINAL ---")
    print(json.dumps(result, indent=2, ensure_ascii=False))
