"""
API FastAPI pour le chatbot Bioforce
"""
import logging
import os
from datetime import datetime
from typing import Dict, List, Any, Optional

import uvicorn
from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import sys
import pathlib
# Ajouter le répertoire parent au path pour pouvoir importer les modules
sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))

from bioforce_scraper.config import LOG_FILE, API_HOST, API_PORT, SCHEDULER_ENABLED, REMINDER_ENABLED, API_ROOT_PATH
from bioforce_scraper.faq_scraper import FAQScraper
from bioforce_scraper.scheduler import SchedulerService
from bioforce_scraper.utils.logger import setup_logger
from bioforce_scraper.utils.reminder_service import ReminderService
from bioforce_scraper.utils.qdrant_connector import QdrantConnector
from bioforce_scraper.utils.embeddings import generate_embeddings
from bioforce_scraper.api.admin import router as admin_router

# Configuration du logger
logger = setup_logger(__name__, LOG_FILE)

# Création de l'application FastAPI
app = FastAPI(
    title="Bioforce Chatbot API",
    description="API pour le chatbot Bioforce",
    version="1.0.0"
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Peut être configuré pour des origines spécifiques en production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclure le router admin
app.include_router(admin_router)

# Servir les fichiers statiques
app.mount("/static", StaticFiles(directory="bioforce_scraper/api/static"), name="static")
os.makedirs("bioforce_scraper/api/static", exist_ok=True)

# Services
scheduler_service = SchedulerService()
reminder_service = ReminderService(app=app)
qdrant = QdrantConnector()

# Modèles Pydantic
class QueryRequest(BaseModel):
    query: str
    user_id: Optional[str] = None
    language: Optional[str] = None
    max_results: Optional[int] = 5
    filters: Optional[Dict[str, Any]] = None

class ScrapeRequest(BaseModel):
    force_update: bool = False
    url: Optional[str] = None

class ReminderRequest(BaseModel):
    user_id: str
    email: Optional[str] = None
    reminder_type: str = "chat"  # "chat" ou "email"

# Routes
@app.get("/")
async def root():
    """Route racine pour vérifier que l'API est en ligne"""
    return {
        "status": "online",
        "timestamp": datetime.now().isoformat(),
        "api_version": "1.0.0"
    }

@app.post("/query")
async def query(request: QueryRequest):
    """Endpoint pour les requêtes au chatbot"""
    try:
        # Générer l'embedding de la requête
        query_embedding = await generate_embeddings(request.query)
        
        if not query_embedding:
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error", 
                    "message": "Erreur lors de la génération de l'embedding"
                }
            )
        
        # Préparer les filtres
        filters = request.filters or {}
        
        # Effectuer la recherche dans Qdrant
        search_results = qdrant.search(
            query_vector=query_embedding,
            limit=request.max_results,
            filter_conditions=filters
        )
        
        # Logger la requête pour analyse ultérieure
        logger.info(f"Requête: '{request.query}' - Résultats: {len(search_results)}")
        
        return {
            "status": "success",
            "query": request.query,
            "results": search_results,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Erreur lors du traitement de la requête: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

@app.post("/scrape/faq")
async def scrape_faq(request: ScrapeRequest, background_tasks: BackgroundTasks):
    """Endpoint pour déclencher un scraping de la FAQ"""
    try:
        # Scraper en tâche de fond pour ne pas bloquer la requête
        background_tasks.add_task(run_faq_scraper, request.force_update)
        
        return {
            "status": "started",
            "message": "Scraping de la FAQ démarré en arrière-plan",
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Erreur lors du démarrage du scraping: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

@app.post("/scrape/full")
async def scrape_full_site(request: ScrapeRequest, background_tasks: BackgroundTasks):
    """Endpoint pour déclencher un scraping complet du site"""
    try:
        # Importer BioforceScraperMain uniquement lorsque c'est nécessaire
        # pour éviter des problèmes d'imports circulaires
        from main import BioforceScraperMain
        
        # Scraper en tâche de fond pour ne pas bloquer la requête
        background_tasks.add_task(run_full_scraper, request.force_update)
        
        return {
            "status": "started",
            "message": "Scraping complet du site démarré en arrière-plan",
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Erreur lors du démarrage du scraping complet: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

@app.post("/reminder/send")
async def send_reminder(request: ReminderRequest, background_tasks: BackgroundTasks):
    """Endpoint pour envoyer un rappel à un utilisateur"""
    try:
        if not REMINDER_ENABLED:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Service de rappels désactivé"}
            )
        
        # Simuler un candidat avec les informations fournies
        candidate = {
            "id": request.user_id,
            "email": request.email,
            "prenom": "Utilisateur",
            "actif": True,
            "temps_inactif_minutes": 5,
            "etape_candidature": "Formulaire"
        }
        
        if request.reminder_type == "chat":
            # Envoyer un rappel dans le chat
            success = await reminder_service.send_chat_reminder(candidate)
        elif request.reminder_type == "email" and request.email:
            # Envoyer un email de rappel
            success = await reminder_service.send_reminder_email(candidate, background_tasks)
        else:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Type de rappel invalide ou email manquant"}
            )
        
        if success:
            return {
                "status": "success",
                "message": f"Rappel {request.reminder_type} envoyé à l'utilisateur {request.user_id}",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": "Échec de l'envoi du rappel"}
            )
    
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi du rappel: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

@app.get("/scheduler/status")
async def get_scheduler_status():
    """Endpoint pour récupérer le statut du planificateur"""
    if not SCHEDULER_ENABLED:
        return {"status": "disabled"}
    
    try:
        status = scheduler_service.get_job_status()
        return {
            "status": "success",
            "data": status,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du statut du planificateur: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

@app.post("/scheduler/run/{job_id}")
async def run_scheduler_job(job_id: str):
    """Endpoint pour déclencher une tâche planifiée"""
    if not SCHEDULER_ENABLED:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Planificateur désactivé"}
        )
    
    try:
        if job_id not in ["faq_update", "full_site_update", "reminder"]:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": f"Tâche inconnue: {job_id}"}
            )
        
        success = scheduler_service.run_job(job_id)
        
        if success:
            return {
                "status": "success",
                "message": f"Tâche {job_id} démarrée",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": f"Échec du démarrage de la tâche {job_id}"}
            )
    
    except Exception as e:
        logger.error(f"Erreur lors du démarrage de la tâche: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

@app.get("/qdrant/stats")
async def get_qdrant_stats():
    """Endpoint pour récupérer les statistiques de Qdrant"""
    try:
        stats = qdrant.get_stats()
        return {
            "status": "success",
            "data": stats,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des statistiques Qdrant: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

# Fonctions d'arrière-plan
async def run_faq_scraper(force_update: bool = False):
    """Exécute le scraping de la FAQ en arrière-plan"""
    try:
        scraper = FAQScraper(force_update=force_update)
        await scraper.run()
    except Exception as e:
        logger.error(f"Erreur dans la tâche d'arrière-plan de scraping FAQ: {e}")

async def run_full_scraper(force_update: bool = False):
    """Exécute le scraping complet du site en arrière-plan"""
    try:
        from main import BioforceScraperMain
        
        scraper = BioforceScraperMain(incremental=not force_update)
        await scraper.run()
    except Exception as e:
        logger.error(f"Erreur dans la tâche d'arrière-plan de scraping complet: {e}")

@app.on_event("startup")
async def startup_event():
    """Événement de démarrage de l'application"""
    logger.info("Démarrage de l'API Bioforce")
    
    # S'assurer que la collection Qdrant existe
    qdrant.ensure_collection()
    
    # Démarrer le planificateur si activé
    if SCHEDULER_ENABLED:
        scheduler_service.start_scheduler()
        logger.info("Planificateur démarré")

@app.on_event("shutdown")
async def shutdown_event():
    """Événement d'arrêt de l'application"""
    logger.info("Arrêt de l'API Bioforce")
    
    # Arrêter le planificateur si activé
    if SCHEDULER_ENABLED:
        scheduler_service.stop_scheduler()
        logger.info("Planificateur arrêté")

def start():
    """Démarre l'application avec uvicorn"""
    uvicorn.run(
        "bioforce_scraper.api.app:app",
        host=API_HOST,
        port=API_PORT,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    start()
