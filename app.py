#app.py


import os
import logging
from dotenv import load_dotenv
import uvicorn
#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Charger les variables d'environnement
load_dotenv()

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
)
logger = logging.getLogger("bioforce_startup")

if __name__ == "__main__":
    # Récupérer les paramètres depuis les variables d'environnement
    host = os.getenv('API_HOST', '0.0.0.0')
    port = int(os.getenv('API_PORT', '8000'))
    env = os.getenv('ENVIRONMENT', 'production')
    
    # Configurer le rechargement automatique uniquement en développement
    reload = env.lower() != 'production'
    
    # Configurer le nombre de workers
    workers = int(os.getenv('API_WORKERS', '1')) if env.lower() == 'production' else 1
    
    # Afficher les paramètres de démarrage
    logger.info("=== DÉMARRAGE DE L'API BIOFORCE ===")
    logger.info(f"Environnement: {env}")
    logger.info(f"Hôte: {host}")
    logger.info(f"Port: {port}")
    logger.info(f"Rechargement automatique: {reload}")
    logger.info(f"Nombre de workers: {workers}")
    
    # Démarrer l'application
    uvicorn.run(
        "bioforce_api_chatbot:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers
    )