"""
Script de diagnostic pour vérifier la connexion à Qdrant et l'état des collections
"""
import os
import asyncio
from dotenv import load_dotenv
from qdrant_client import AsyncQdrantClient

# Chargement des variables d'environnement
load_dotenv()

# Configuration Qdrant
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

COLLECTIONS_TO_CHECK = [
    "BIOFORCE",         # Collection mentionnée dans .env
    "BIOFORCE_ALL",     # Collection mentionnée dans votre message
]

async def check_qdrant():
    """Vérifie la connexion à Qdrant et l'état des collections"""
    print(f"🔍 Test de connexion à Qdrant URL: {QDRANT_URL}")
    
    if not QDRANT_URL or not QDRANT_API_KEY:
        print("❌ ERREUR: Variables d'environnement Qdrant manquantes ou invalides")
        return
        
    try:
        # Initialisation du client Qdrant
        client = AsyncQdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        
        # Test de connexion
        print("⏳ Test de connexion au serveur Qdrant...")
        collections = await client.get_collections()
        print(f"✅ Connexion réussie! {len(collections.collections)} collections trouvées.")
        
        # Liste des collections existantes
        collection_names = [collection.name for collection in collections.collections]
        print(f"\n📋 Collections disponibles sur le serveur: {collection_names}\n")
        
        # Vérification des collections spécifiques
        for collection_name in COLLECTIONS_TO_CHECK:
            if collection_name in collection_names:
                print(f"✅ Collection '{collection_name}' trouvée")
                
                # Obtenir les informations sur la collection
                collection_info = await client.get_collection(collection_name=collection_name)
                print(f"   - Points: {collection_info.vectors_count}")
                print(f"   - Dimension des vecteurs: {collection_info.config.params.vectors.size}")
                
                # Compter le nombre d'éléments
                count = await client.count(collection_name=collection_name)
                print(f"   - Nombre de documents: {count.count}")
                
                # Récupérer un exemple de document pour vérifier la structure
                try:
                    points = await client.scroll(
                        collection_name=collection_name,
                        limit=1,
                        with_payload=True,
                        with_vectors=False
                    )
                    
                    if points[0]:
                        print(f"   - Structure d'un document (clés): {list(points[0][0].payload.keys())}")
                    else:
                        print("   - Aucun document trouvé dans la collection")
                        
                except Exception as e:
                    print(f"   - Erreur lors de la récupération d'un exemple: {str(e)}")
            else:
                print(f"❌ Collection '{collection_name}' NON trouvée")
        
    except Exception as e:
        print(f"❌ ERREUR de connexion à Qdrant: {str(e)}")
        if "Connection refused" in str(e):
            print("\n⚠️ Le serveur Qdrant semble inaccessible. Vérifiez l'URL et les paramètres réseau.")
        elif "401" in str(e) or "Unauthorized" in str(e):
            print("\n⚠️ Problème d'authentification. Vérifiez votre clé API.")
        elif "404" in str(e):
            print("\n⚠️ Ressource non trouvée. Vérifiez l'URL.")

if __name__ == "__main__":
    asyncio.run(check_qdrant())
