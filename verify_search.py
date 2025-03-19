"""
Vérification finale de la recherche Qdrant
"""
import asyncio
import json
import os
from dotenv import load_dotenv
from qdrant_client import AsyncQdrantClient
from openai import AsyncOpenAI

# Chargement des variables d'environnement
load_dotenv()
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "BIOFORCE")

# Initialisation des clients
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
qdrant_client = None

async def generate_embedding(text):
    """Génère un embedding pour le texte donné"""
    response = await openai_client.embeddings.create(
        input=text,
        model="text-embedding-ada-002"
    )
    return response.data[0].embedding

async def search_with_real_embedding():
    """Recherche avec un vrai embedding généré par OpenAI"""
    global qdrant_client
    
    # Initialiser le client Qdrant
    print(f"Connexion à Qdrant: {QDRANT_URL}")
    qdrant_client = AsyncQdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    
    # Vérifier la connexion
    collections = await qdrant_client.get_collections()
    collection_names = [c.name for c in collections.collections]
    print(f"Collections disponibles: {', '.join(collection_names)}")
    
    # Générer un embedding réel pour une requête pertinente
    query = "formation logistique humanitaire"
    print(f"\nGénération d'embedding pour: '{query}'")
    vector = await generate_embedding(query)
    
    # Recherche avec l'embedding réel
    print(f"Recherche dans la collection {COLLECTION_NAME}...")
    results = await qdrant_client.search(
        collection_name=COLLECTION_NAME,
        query_vector=vector,
        limit=3
    )
    
    # Sauvegarder les résultats dans un fichier
    print(f"Nombre de résultats: {len(results)}")
    
    # Créer un dictionnaire pour stocker les résultats
    search_results = []
    for i, result in enumerate(results, 1):
        res = {
            "index": i,
            "score": result.score,
            "payload": result.payload
        }
        search_results.append(res)
        print(f"Résultat {i}: Score = {result.score:.4f}")
    
    # Écrire les résultats dans un fichier JSON
    with open("search_results.json", "w", encoding="utf-8") as f:
        json.dump(search_results, f, ensure_ascii=False, indent=2)
    
    print("\n✅ Résultats sauvegardés dans 'search_results.json'")
    return len(results) > 0

if __name__ == "__main__":
    success = asyncio.run(search_with_real_embedding())
    print(f"\n{'✅ Recherche réussie!' if success else '❌ Échec de la recherche.'}")
