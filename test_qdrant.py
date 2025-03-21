"""
Test de connexion à Qdrant
"""
import os
import sys
import asyncio
import logging
from dotenv import load_dotenv
from qdrant_client import AsyncQdrantClient

# Configuration du logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Chargement des variables d'environnement
load_dotenv('.env')

async def test_qdrant_connection():
    """Teste la connexion à Qdrant"""
    # Récupérer les variables d'environnement
    qdrant_url = os.getenv('QDRANT_URL')
    qdrant_api_key = os.getenv('QDRANT_API_KEY')
    collection_name = os.getenv('QDRANT_COLLECTION', 'BIOFORCE')
    
    logger.info(f"URL Qdrant: {qdrant_url}")
    logger.info(f"API Key Qdrant: {qdrant_api_key[:10]}... (tronquée pour sécurité)")
    
    if not qdrant_url or not qdrant_api_key:
        logger.error("Variables d'environnement QDRANT_URL ou QDRANT_API_KEY manquantes")
        return False
    
    try:
        # Connexion à Qdrant
        client = AsyncQdrantClient(url=qdrant_url, api_key=qdrant_api_key, timeout=30)
        
        # Vérifier que la connexion fonctionne
        collections = await client.get_collections()
        collection_names = [collection.name for collection in collections.collections]
        
        # Vérifier que la collection existe
        if collection_name not in collection_names:
            logger.warning(f"Collection {collection_name} non trouvée. Collections disponibles: {', '.join(collection_names)}")
            return False
        
        # Récupérer le nombre de points dans la collection
        count = await client.count(collection_name=collection_name)
        logger.info(f"Nombre de points dans la collection: {count.count}")
        
        return True
        
    except Exception as e:
        logger.error(f"Erreur de connexion à Qdrant: {e}")
        return False

# Point d'entrée principal
async def main():
    """Fonction principale"""
    success = await test_qdrant_connection()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
