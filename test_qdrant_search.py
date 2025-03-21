"""
Test simple de recherche Qdrant
"""
import os
import asyncio
from dotenv import load_dotenv
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient

# Chargement des variables d'environnement
load_dotenv()

# Variables de configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
QDRANT_URL = os.getenv('QDRANT_URL')
QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')
COLLECTION_NAME = os.getenv('QDRANT_COLLECTION', 'BIOFORCE')

# Initialisation des clients
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
qdrant_client = AsyncQdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

async def generate_embedding(text: str):
    """Génère un embedding pour le texte donné"""
    response = await openai_client.embeddings.create(
        input=text,
        model="text-embedding-ada-002"
    )
    return response.data[0].embedding

async def test_search():
    print("Test de connexion à Qdrant")
    print(f"URL: {QDRANT_URL}")
    print(f"Collection: {COLLECTION_NAME}")
    
    try:
        # Vérifier si la collection existe
        collections = await qdrant_client.get_collections()
        collection_names = [collection.name for collection in collections.collections]
        
        print(f"Collections disponibles: {collection_names}")
        
        if COLLECTION_NAME in collection_names:
            print(f"La collection {COLLECTION_NAME} existe!")
            
            # Obtenir des informations sur la collection
            collection_info = await qdrant_client.get_collection(collection_name=COLLECTION_NAME)
            print(f"Info collection: {collection_info}")
            
            # Compter les points dans la collection
            count = await qdrant_client.count(collection_name=COLLECTION_NAME)
            print(f"Nombre de points dans la collection: {count.count}")
            
            # Faire une recherche simple
            query = "Comment s'inscrire à une formation?"
            print(f"\nGénération d'embedding pour la requête: '{query}'")
            vector = await generate_embedding(query)
            
            print("Recherche dans Qdrant...")
            search_result = await qdrant_client.search(
                collection_name=COLLECTION_NAME,
                query_vector=vector,
                limit=2
            )
            
            print(f"Résultats trouvés: {len(search_result)}")
            for i, result in enumerate(search_result):
                print(f"\nRésultat {i+1} (Score: {result.score:.4f}):")
                for key, value in result.payload.items():
                    print(f"  - {key}")
            
            return True
        else:
            print(f"La collection {COLLECTION_NAME} n'existe pas!")
            return False
            
    except Exception as e:
        print(f"Erreur: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_search())
    print(f"\nTest réussi: {result}")
