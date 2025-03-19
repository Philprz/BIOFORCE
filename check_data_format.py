"""
Vérification du format des données dans Qdrant via recherche simple
"""
import asyncio
import json
import os
from dotenv import load_dotenv
from qdrant_client import AsyncQdrantClient

# Chargement des variables d'environnement
load_dotenv()
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

async def examine_collection(client, collection_name):
    """Examine la structure des données dans une collection via recherche"""
    print(f"\n{'='*50}")
    print(f"ANALYSE DE LA COLLECTION: {collection_name}")
    print(f"{'='*50}")
    
    try:
        # Obtenir les informations sur la collection
        collection_info = await client.get_collection(collection_name=collection_name)
        print(f"Nombre de vecteurs: {collection_info.vectors_count}")
        
        # Créer un vecteur de test pour la recherche
        test_vector = [0.1] * 1536  # Dimension pour ada-002
        
        print(f"\nRecherche dans la collection {collection_name}...")
        results = await client.search(
            collection_name=collection_name,
            query_vector=test_vector,
            limit=5
        )
        
        print(f"Nombre de résultats: {len(results)}")
        
        if not results:
            print("Aucun résultat trouvé.")
            return
        
        # Analyser et afficher les résultats
        print("\nSTRUCTURE DES DONNÉES:")
        
        # Obtenir tous les champs uniques dans les payloads
        all_fields = set()
        for result in results:
            if hasattr(result, 'payload') and result.payload:
                all_fields.update(result.payload.keys())
        
        print(f"Champs détectés: {', '.join(sorted(all_fields))}")
        
        # Analyser chaque résultat
        for i, result in enumerate(results, 1):
            print(f"\n--- RÉSULTAT {i} ---")
            print(f"Score: {result.score:.4f}")
            
            if not hasattr(result, 'payload') or not result.payload:
                print("Aucun payload trouvé pour ce résultat.")
                continue
                
            payload = result.payload
            
            # Afficher chaque champ avec des valeurs tronquées pour les textes longs
            for field in sorted(payload.keys()):
                value = payload[field]
                if isinstance(value, str):
                    if len(value) > 100:
                        display_value = f"{value[:100]}..."
                    else:
                        display_value = value
                else:
                    display_value = str(value)
                    
                print(f"{field}: {display_value}")
        
        # Afficher un exemple complet
        print("\nEXEMPLE DE DOCUMENT COMPLET (PREMIER RÉSULTAT):")
        if results and hasattr(results[0], 'payload') and results[0].payload:
            print(json.dumps(results[0].payload, indent=2, ensure_ascii=False))
        else:
            print("Le premier résultat ne contient pas de payload.")
            
    except Exception as e:
        print(f"Erreur lors de l'analyse de la collection {collection_name}: {str(e)}")

async def main():
    """Fonction principale"""
    print(f"Connexion à Qdrant: {QDRANT_URL}")
    client = AsyncQdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    
    try:
        # Obtenir la liste des collections
        collections = await client.get_collections()
        collection_names = [c.name for c in collections.collections]
        print(f"Collections disponibles: {', '.join(collection_names)}")
        
        # Analyser chaque collection
        for collection_name in collection_names:
            await examine_collection(client, collection_name)
            
    except Exception as e:
        print(f"Erreur: {str(e)}")
    
    print("\nAnalyse terminée.")

if __name__ == "__main__":
    asyncio.run(main())
