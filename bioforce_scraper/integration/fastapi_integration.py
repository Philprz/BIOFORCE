"""
Module d'intégration avec FastAPI pour le scraper Bioforce
"""
import os
import json
from datetime import datetime
from typing import Dict, List, Optional

import sys
import pathlib
# Ajouter le répertoire parent au path pour pouvoir importer les modules
sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))

from bioforce_scraper.config import DATA_DIR
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel

from integration.knowledge_updater import KnowledgeUpdater
from utils.content_tracker import ContentTracker

router = APIRouter(
    prefix="/scraper",
    tags=["scraper"],
    responses={404: {"description": "Not found"}},
)

# Modèles Pydantic pour les requêtes et réponses
class ScrapeRequest(BaseModel):
    force_update: bool = False
    specific_urls: Optional[List[str]] = None
    pdf_only: bool = False

class ScrapeResponse(BaseModel):
    job_id: str
    status: str
    message: str

class ScrapeStatus(BaseModel):
    job_id: str
    status: str
    progress: Optional[float] = None
    start_time: str
    end_time: Optional[str] = None
    stats: Optional[Dict] = None
    error: Optional[str] = None

# Stockage des tâches en cours
scrape_jobs = {}

def get_knowledge_updater():
    """
    Factory pour obtenir une instance du KnowledgeUpdater
    """
    return KnowledgeUpdater(
        qdrant_url=os.getenv("QDRANT_URL"),
        qdrant_api_key=os.getenv("QDRANT_API_KEY"),
        collection_name=os.getenv("QDRANT_COLLECTION", "bioforce_knowledge")
    )

@router.get("/status", response_model=List[ScrapeStatus])
async def get_all_jobs_status():
    """
    Récupère le statut de toutes les tâches de scraping
    """
    return list(scrape_jobs.values())

@router.get("/status/{job_id}", response_model=ScrapeStatus)
async def get_job_status(job_id: str):
    """
    Récupère le statut d'une tâche de scraping spécifique
    """
    if job_id not in scrape_jobs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job {} not found".format(job_id)
        )
    
    return scrape_jobs[job_id]

@router.post("/update", response_model=ScrapeResponse)
async def update_knowledge_base(
    request: ScrapeRequest,
    background_tasks: BackgroundTasks,
    updater: KnowledgeUpdater = Depends(get_knowledge_updater)
):
    """
    Lance une tâche de mise à jour de la base de connaissances
    """
    # Générer un ID de tâche
    job_id = "scrape_{}".format(datetime.now().strftime('%Y%m%d_%H%M%S'))
    
    # Enregistrer la tâche
    scrape_jobs[job_id] = ScrapeStatus(
        job_id=job_id,
        status="queued",
        start_time=datetime.now().isoformat(),
        progress=0.0
    )
    
    # Lancer la tâche en arrière-plan
    background_tasks.add_task(
        run_update_task,
        job_id=job_id,
        updater=updater,
        force_update=request.force_update,
        specific_urls=request.specific_urls,
        pdf_only=request.pdf_only
    )
    
    return ScrapeResponse(
        job_id=job_id,
        status="queued",
        message="Knowledge base update task started"
    )

@router.post("/sync", response_model=ScrapeResponse)
async def sync_knowledge_base(
    background_tasks: BackgroundTasks,
    updater: KnowledgeUpdater = Depends(get_knowledge_updater)
):
    """
    Lance une tâche de synchronisation initiale de la base de connaissances
    """
    # Générer un ID de tâche
    job_id = "sync_{}".format(datetime.now().strftime('%Y%m%d_%H%M%S'))
    
    # Enregistrer la tâche
    scrape_jobs[job_id] = ScrapeStatus(
        job_id=job_id,
        status="queued",
        start_time=datetime.now().isoformat(),
        progress=0.0
    )
    
    # Lancer la tâche en arrière-plan
    background_tasks.add_task(
        run_sync_task,
        job_id=job_id,
        updater=updater
    )
    
    return ScrapeResponse(
        job_id=job_id,
        status="queued",
        message="Knowledge base sync task started"
    )

@router.get("/stats")
async def get_scraper_stats():
    """
    Récupère des statistiques sur le contenu tracké
    """
    tracker = ContentTracker()
    stats = {
        "total_urls": tracker.count_total_urls(),
        "content_types": tracker.count_by_content_type(),
        "content_languages": tracker.count_by_language(),
        "content_categories": tracker.count_by_category(),
        "timestamp": datetime.now().isoformat()
    }
    return stats

@router.get("/reports")
async def get_change_reports():
    """
    Récupère la liste des rapports de changement
    """
    reports_dir = os.path.join(DATA_DIR, "reports")
    if not os.path.exists(reports_dir):
        return []
    
    reports = []
    for filename in os.listdir(reports_dir):
        if filename.endswith(".json") and filename.startswith("changes_"):
            file_path = os.path.join(reports_dir, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    report = json.load(f)
                
                reports.append({
                    "filename": filename,
                    "timestamp": report.get("timestamp", ""),
                    "new_count": len(report.get("new_content", [])),
                    "updated_count": len(report.get("updated_content", [])),
                    "unchanged_count": report.get("unchanged_count", 0),
                    "total_count": report.get("total_count", 0)
                })
            except Exception:
                continue
    
    # Trier par timestamp décroissant
    reports.sort(key=lambda x: x["timestamp"], reverse=True)
    return reports

@router.get("/reports/{report_name}")
async def get_report_details(report_name: str):
    """
    Récupère les détails d'un rapport de changement spécifique
    """
    if not report_name.endswith(".json") or not report_name.startswith("changes_"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid report name format"
        )
    
    file_path = os.path.join(DATA_DIR, "reports", report_name)
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report {} not found".format(report_name)
        )
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            report = json.load(f)
        return report
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error reading report"
        )

async def run_update_task(
    job_id: str,
    updater: KnowledgeUpdater,
    force_update: bool = False,
    specific_urls: Optional[List[str]] = None,
    pdf_only: bool = False
):
    """
    Exécute la tâche de mise à jour dans un thread séparé
    """
    try:
        # Mettre à jour le statut
        scrape_jobs[job_id]["status"] = "running"
        scrape_jobs[job_id]["progress"] = 0.1
        
        # Configurer le scraper
        updater.scraper.force_update = force_update
        if specific_urls:
            updater.scraper.specific_urls = specific_urls
        updater.scraper.pdf_only = pdf_only
        
        # Exécuter la mise à jour
        stats = await updater.update_knowledge_base()
        
        # Mettre à jour le statut final
        scrape_jobs[job_id]["status"] = "completed"
        scrape_jobs[job_id]["end_time"] = datetime.now().isoformat()
        scrape_jobs[job_id]["progress"] = 100.0
        scrape_jobs[job_id]["stats"] = stats
        
    except Exception:
        # Gérer les erreurs
        scrape_jobs[job_id]["status"] = "failed"
        scrape_jobs[job_id]["end_time"] = datetime.now().isoformat()
        scrape_jobs[job_id]["error"] = ""

async def run_sync_task(job_id: str, updater: KnowledgeUpdater):
    """
    Exécute la tâche de synchronisation initiale dans un thread séparé
    """
    try:
        # Mettre à jour le statut
        scrape_jobs[job_id]["status"] = "running"
        scrape_jobs[job_id]["progress"] = 0.1
        
        # Exécuter la synchronisation
        stats = await updater.perform_initial_sync()
        
        # Mettre à jour le statut final
        scrape_jobs[job_id]["status"] = "completed"
        scrape_jobs[job_id]["end_time"] = datetime.now().isoformat()
        scrape_jobs[job_id]["progress"] = 100.0
        scrape_jobs[job_id]["stats"] = stats
        
    except Exception:
        # Gérer les erreurs
        scrape_jobs[job_id]["status"] = "failed"
        scrape_jobs[job_id]["end_time"] = datetime.now().isoformat()
        scrape_jobs[job_id]["error"] = ""
