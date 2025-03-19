"""
Test simplifié de recherche Qdrant
"""
import asyncio
import json
from qdrant_client import AsyncQdrantClient
import os
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "BIOFORCE")

async def main():
    print(f"Connexion à Qdrant: {QDRANT_URL} | Collection: {COLLECTION_NAME}")
    client = AsyncQdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    
    # Test de connexion
    collections = await client.get_collections()
    collection_names = [c.name for c in collections.collections]
    print(f"Collections disponibles: {collection_names}")
    
    # Simuler un vecteur d'embedding (utiliser un vecteur de test rempli de 0.1)
    # La dimension doit être 1536 pour correspondre à l'embedding d'OpenAI ada-002
    test_vector = [0.1] * 1536
    
    # Recherche simple avec le vecteur de test
    print(f"\nRecherche dans la collection {COLLECTION_NAME}...")
    results = await client.search(
        collection_name=COLLECTION_NAME,
        query_vector=test_vector,
        limit=3
    )
    
    # Afficher les résultats
    print(f"Nombre de résultats: {len(results)}")
    for i, result in enumerate(results, 1):
        print(f"\nRésultat {i}:")
        print(f"Score: {result.score}")
        print(f"Payload: {json.dumps(result.payload, ensure_ascii=False, indent=2)[:500]}...")

if __name__ == "__main__":
    asyncio.run(main())
