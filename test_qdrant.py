"""
Script de test pour vérifier la connexion à Qdrant
"""
import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
import logging

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Chargement explicite des variables d'environnement
load_dotenv('.env')

# Afficher les variables pour débogage
qdrant_url = os.getenv('QDRANT_URL')
qdrant_api_key = os.getenv('QDRANT_API_KEY')
collection_name = os.getenv('QDRANT_COLLECTION')

logger.info(f"URL Qdrant: {qdrant_url}")
logger.info(f"API Key Qdrant: {qdrant_api_key[:10]}... (tronquée pour sécurité)")
logger.info(f"Collection: {collection_name}")

# Tenter de se connecter à Qdrant
try:
    client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
    logger.info("Connexion à Qdrant réussie!")
    
    # Vérifier si la collection existe
    collections = client.get_collections()
    collection_names = [collection.name for collection in collections.collections]
    
    logger.info(f"Collections disponibles: {collection_names}")
    
    if collection_name in collection_names:
        logger.info(f"La collection {collection_name} existe!")
        # Obtenir des informations sur la collection
        collection_info = client.get_collection(collection_name=collection_name)
        logger.info(f"Info collection: {collection_info}")
        
        # Compter les points dans la collection
        count = client.count(collection_name=collection_name)
        logger.info(f"Nombre de points dans la collection: {count.count}")
    else:
        logger.warning(f"La collection {collection_name} n'existe pas!")
        
except Exception as e:
    logger.error(f"Erreur de connexion à Qdrant: {e}")
