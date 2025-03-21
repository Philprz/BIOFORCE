"""
Script pour démarrer l'API FastAPI du chatbot Bioforce
"""
import os
import sys
import logging
import traceback
from dotenv import load_dotenv
import uvicorn
import importlib.util

# Configuration du logging pour le démarrage
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
)
logger = logging.getLogger("bioforce_startup")

try:
    # Charger les variables d'environnement
    logger.info("Chargement des variables d'environnement...")
    load_dotenv()
    
    # Journaliser les variables d'environnement critiques (sans exposer les valeurs)
    env_vars = [
        "OPENAI_API_KEY", 
        "QDRANT_URL", 
        "QDRANT_API_KEY", 
        "QDRANT_COLLECTION", 
        "QDRANT_COLLECTION_ALL",
        "ENVIRONMENT",
        "VECTOR_SIZE"
    ]
    
    for var in env_vars:
        value = os.getenv(var)
        if value:
            if "API_KEY" in var:
                logger.info(f"✓ Variable d'environnement {var} définie: {value[:5]}...")
            else:
                logger.info(f"✓ Variable d'environnement {var} définie: {value}")
        else:
            logger.warning(f"✗ Variable d'environnement {var} non définie ou vide")
    
    # Ajouter le répertoire courant au path
    current_dir = os.path.abspath('.')
    logger.info(f"Ajout du répertoire {current_dir} au sys.path")
    sys.path.append(current_dir)
    
    # Vérifier l'importation des modules critiques
    logger.info("Vérification des modules critiques...")
    try:
        from bioforce_scraper.config import API_HOST, API_PORT, API_WORKERS
        logger.info(f"Configuration chargée: API_HOST={API_HOST}, API_PORT={API_PORT}, API_WORKERS={API_WORKERS}")
    except ImportError as e:
        logger.error(f"Échec du chargement de la configuration: {str(e)}")
        sys.exit(1)
    
    # Vérifier la présence des modules d'API
    try:
        logger.info("Vérification des modules d'API...")
        if importlib.util.find_spec("bioforce_scraper.api.app"):
            logger.info("Module d'API trouvé avec succès")
        else:
            logger.error("Module d'API non trouvé")
            sys.exit(1)
    except ImportError as e:
        logger.error(f"Échec du chargement du module d'API: {str(e)}")
        sys.exit(1)
    
    # Vérifier la connexion à Qdrant
    try:
        logger.info("Test de l'importation du connecteur Qdrant...")
        if importlib.util.find_spec("bioforce_scraper.utils.qdrant_connector"):
            logger.info("Module QdrantConnector trouvé avec succès")
        else:
            logger.warning("Module QdrantConnector non trouvé")
    except ImportError as e:
        logger.error(f"Échec de l'importation du connecteur Qdrant: {str(e)}")
        # Ne pas quitter, car cela sera géré par l'application
    
    if __name__ == "__main__":
        # Déterminer l'environnement
        env = os.environ.get("ENV", "development")
        workers = API_WORKERS if env == "production" else 1
        reload = env != "production"  # Activer le rechargement uniquement en développement
        
        logger.info("=== CONFIGURATION DU DÉMARRAGE ===")
        logger.info(f"Environnement: {env}")
        logger.info(f"Hôte: {API_HOST}")
        logger.info(f"Port: {API_PORT}")
        logger.info(f"Nombre de workers: {workers}")
        logger.info(f"Rechargement automatique: {reload}")
        logger.info("=== DÉMARRAGE DE L'API BIOFORCE ===")
        
        uvicorn.run(
            "bioforce_scraper.api.app:app",
            host=API_HOST,
            port=API_PORT,
            workers=workers,
            reload=reload,
            log_level="debug"  # Définir le niveau de journalisation d'uvicorn à debug
        )
except Exception as e:
    logger.critical(f"Erreur critique lors du démarrage: {str(e)}")
    logger.critical(f"Type d'erreur: {type(e).__name__}")
    logger.critical(f"Stack trace: {traceback.format_exc()}")
    sys.exit(1)
