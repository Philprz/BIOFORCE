"""
Script pour démarrer l'API FastAPI du chatbot Bioforce
"""
import os
import sys
import uvicorn

# Ajouter le répertoire courant au path
sys.path.append(os.path.abspath('.'))

from bioforce_scraper.config import API_HOST, API_PORT, API_WORKERS

if __name__ == "__main__":
    print(f"Démarrage de l'API Bioforce sur {API_HOST}:{API_PORT}")
    uvicorn.run(
        "bioforce_scraper.api.app:app",
        host=API_HOST,
        port=API_PORT,
        workers=API_WORKERS if os.environ.get("ENV") == "production" else 1,
        reload=True
    )
