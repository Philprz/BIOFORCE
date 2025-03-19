"""
Vérification finale de la solution de mappage des champs Qdrant
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

async def generate_embedding(text, client):
    """Génère un embedding pour le texte donné"""
    response = await client.embeddings.create(
        input=text,
        model="text-embedding-ada-002"
    )
    return response.data[0].embedding

async def main():
    """Test de vérification finale"""
    print(f"Connexion à Qdrant: {QDRANT_URL} | Collection: {COLLECTION_NAME}")
    
    # Initialisation des clients
    qdrant_client = AsyncQdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    
    # Test avec une question simple
    query = "Comment postuler à une formation Bioforce ?"
    print(f"\nQuestion test: '{query}'")
    
    # Générer l'embedding
    vector = await generate_embedding(query, openai_client)
    
    # Effectuer la recherche
    results = await qdrant_client.search(
        collection_name=COLLECTION_NAME,
        query_vector=vector,
        limit=3
    )
    
    print(f"Nombre de résultats: {len(results)}")
    
    # Analyser et afficher les résultats bruts du client Qdrant
    print("\n=== DONNÉES BRUTES DE QDRANT ===")
    for i, result in enumerate(results, 1):
        print(f"\nRÉSULTAT {i}")
        print(f"Score: {result.score:.4f}")
        
        # Afficher tous les champs du payload
        if hasattr(result, 'payload') and result.payload:
            print("Champs disponibles:")
            for key, value in result.payload.items():
                # Tronquer les valeurs longues
                if isinstance(value, str) and len(value) > 100:
                    display_value = f"{value[:100]}..."
                else:
                    display_value = str(value)
                print(f"  {key}: {display_value}")
        else:
            print("Aucun payload trouvé")
    
    print("\n=== TRANSFORMATION SELON NOTRE SOLUTION ===")
    for i, result in enumerate(results, 1):
        print(f"\nRÉSULTAT {i}")
        print(f"Score: {result.score:.4f}")
        
        # Appliquer la transformation de champs que nous avons implémentée
        transformed = {
            "score": result.score,
            "question": result.payload.get("title", "N/A"),  # Utiliser title comme question
            "answer": result.payload.get("content", "N/A"),  # Utiliser content comme answer
            "category": result.payload.get("category", "N/A"),
            "url": result.payload.get("url", "N/A")
        }
        
        # Afficher les champs transformés
        print("Après transformation:")
        for key, value in transformed.items():
            if key in ['question', 'answer'] and isinstance(value, str) and len(value) > 100:
                print(f"  {key}: {value[:100]}...")
            else:
                print(f"  {key}: {value}")
    
    # Enregistrer un exemple complet pour analyse
    with open("exemple_transformation.json", "w", encoding="utf-8") as f:
        if results:
            # Sélectionner le premier résultat
            result = results[0]
            
            # Créer l'objet de comparaison
            comparison = {
                "original": {
                    "score": result.score,
                    "payload": result.payload
                },
                "transformed": {
                    "score": result.score,
                    "question": result.payload.get("title", "N/A"),
                    "answer": result.payload.get("content", "N/A"),
                    "category": result.payload.get("category", "N/A"),
                    "url": result.payload.get("url", "N/A")
                }
            }
            
            # Écrire dans le fichier
            json.dump(comparison, f, ensure_ascii=False, indent=2)
            print("\nExemple complet enregistré dans 'exemple_transformation.json'")

if __name__ == "__main__":
    asyncio.run(main())
