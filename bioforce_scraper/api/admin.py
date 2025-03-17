"""
Module pour l'interface administrateur du projet Bioforce
"""
import asyncio
import os
import sys
import subprocess
import platform
from typing import Dict, List, Any, Optional
from datetime import datetime

import uvicorn
from fastapi import APIRouter, Request, Form, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# Ajout du répertoire parent au path pour les importations
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from bioforce_scraper.config import VERSION, GITHUB_REPO
from bioforce_scraper.utils.qdrant_connector import QdrantConnector

# Création du router FastAPI
router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    responses={404: {"description": "Not found"}},
)

# Initialisation des templates
templates = Jinja2Templates(directory="bioforce_scraper/api/templates")
os.makedirs("bioforce_scraper/api/templates", exist_ok=True)

# Création de l'instance QdrantConnector
qdrant = QdrantConnector()

class SystemInfo(BaseModel):
    """Informations système"""
    version: str
    python_version: str
    platform: str
    github_repo: str
    current_time: str
    uptime: Optional[str] = None

class GitHubUpdateResult(BaseModel):
    """Résultat de la mise à jour GitHub"""
    success: bool
    message: str
    details: Optional[str] = None

def get_system_info() -> SystemInfo:
    """Obtient les informations système"""
    return SystemInfo(
        version=VERSION,
        python_version=sys.version.split()[0],
        platform=platform.platform(),
        github_repo=GITHUB_REPO,
        current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        uptime="N/A"  # TODO: Implémenter le calcul du temps d'activité
    )

async def update_from_github() -> GitHubUpdateResult:
    """Met à jour le code depuis GitHub"""
    try:
        if not GITHUB_REPO:
            return GitHubUpdateResult(
                success=False,
                message="Configuration GitHub manquante",
                details="GITHUB_REPO n'est pas défini dans config.py"
            )
        
        # Vérifier que git est installé
        try:
            process = await asyncio.create_subprocess_exec(
                "git", "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                return GitHubUpdateResult(
                    success=False,
                    message="Git n'est pas installé ou n'est pas dans le PATH",
                    details=stderr.decode() if stderr else "Commande git --version a échoué"
                )
        except Exception as e:
            return GitHubUpdateResult(
                success=False,
                message="Erreur lors de la vérification de Git",
                details=str(e)
            )
        
        # Vérifier que le répertoire est un dépôt git
        try:
            process = await asyncio.create_subprocess_exec(
                "git", "rev-parse", "--is-inside-work-tree",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0 or stdout.decode().strip() != "true":
                return GitHubUpdateResult(
                    success=False,
                    message="Le répertoire n'est pas un dépôt Git valide",
                    details=stderr.decode() if stderr else "Pas un dépôt Git"
                )
        except Exception as e:
            return GitHubUpdateResult(
                success=False,
                message="Erreur lors de la vérification du dépôt Git",
                details=str(e)
            )
        
        # Construction de la commande git pull
        cmd = ["git", "pull"]
        
        # Obtenir le répertoire racine du projet
        project_root = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        
        # Exécution de la commande
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=project_root
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            output = stdout.decode()
            if "Already up to date" in output:
                return GitHubUpdateResult(
                    success=True,
                    message="Le code est déjà à jour",
                    details=output
                )
            else:
                return GitHubUpdateResult(
                    success=True,
                    message="Mise à jour réussie",
                    details=output
                )
        else:
            return GitHubUpdateResult(
                success=False,
                message="Échec de la mise à jour",
                details=stderr.decode()
            )
    except Exception as e:
        return GitHubUpdateResult(
            success=False,
            message="Erreur lors de la mise à jour",
            details=str(e)
        )

async def run_command(command: List[str]) -> Dict[str, Any]:
    """Exécute une commande système et retourne le résultat"""
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        return {
            "success": process.returncode == 0,
            "stdout": stdout.decode(),
            "stderr": stderr.decode(),
            "returncode": process.returncode
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Page principale du tableau de bord administrateur"""
    system_info = get_system_info()
    
    # Obtenir les statistiques Qdrant
    try:
        qdrant_stats = await qdrant.get_stats()
    except Exception as e:
        qdrant_stats = {"error": str(e)}
    
    return templates.TemplateResponse(
        "admin_dashboard.html",
        {
            "request": request,
            "system_info": system_info,
            "qdrant_stats": qdrant_stats
        }
    )

@router.post("/update-github")
async def update_github_route(background_tasks: BackgroundTasks):
    """Route pour mettre à jour depuis GitHub"""
    result = await update_from_github()
    return result

@router.post("/run-faq-scraper")
async def run_faq_scraper_route(background_tasks: BackgroundTasks, force_update: bool = Form(False)):
    """Route pour lancer le scraper de FAQ"""
    # Prépare la commande à exécuter
    python_exec = sys.executable
    cmd = [python_exec, "-m", "bioforce_scraper.run_scraper", "--faq-only"]
    if force_update:
        cmd.append("--force")
    
    # Exécute la commande en arrière-plan
    background_tasks.add_task(run_command, cmd)
    
    return {
        "status": "started",
        "message": "Scraper de FAQ démarré en arrière-plan",
        "force_update": force_update
    }

@router.post("/run-full-scraper")
async def run_full_scraper_route(background_tasks: BackgroundTasks, force_update: bool = Form(False)):
    """Route pour lancer le scraper complet"""
    # Prépare la commande à exécuter
    python_exec = sys.executable
    cmd = [python_exec, "-m", "bioforce_scraper.run_scraper", "--full"]
    if force_update:
        cmd.append("--force")
    
    # Exécute la commande en arrière-plan
    background_tasks.add_task(run_command, cmd)
    
    return {
        "status": "started",
        "message": "Scraper complet démarré en arrière-plan",
        "force_update": force_update
    }

@router.get("/qdrant-stats")
async def get_qdrant_stats_route():
    """Route pour obtenir les statistiques Qdrant"""
    try:
        stats = await qdrant.get_stats()
        return {
            "status": "success",
            "data": stats
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
