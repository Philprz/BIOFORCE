"""
Module pour l'interface administrateur du projet Bioforce
"""
import os
import sys
import platform
import datetime
import asyncio
import json
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Request, BackgroundTasks, Form, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import logging

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

# Initialisation des templates avec un chemin absolu
current_dir = os.path.dirname(os.path.abspath(__file__))
templates_dir = os.path.join(current_dir, "templates")
templates = Jinja2Templates(directory=templates_dir)
os.makedirs(templates_dir, exist_ok=True)

# Création de l'instance QdrantConnector
qdrant = QdrantConnector()
logger = logging.getLogger(__name__)

# Initialisation du logger
logging.basicConfig(level=logging.INFO)

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

class EmailTemplate(BaseModel):
    """Modèle de template d'email"""
    type: str
    subject: str
    content: str
    last_updated: Optional[str] = None

def get_system_info() -> SystemInfo:
    """Obtient les informations système"""
    return SystemInfo(
        version=VERSION,
        python_version=sys.version.split()[0],
        platform=platform.platform(),
        github_repo=GITHUB_REPO,
        current_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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

@router.post("/git-update", response_model=GitHubUpdateResult)
async def update_github_route(background_tasks: BackgroundTasks):
    """Met à jour le code depuis GitHub"""
    result = await update_from_github()
    return result

@router.get("/system-info", response_model=SystemInfo)
async def get_system_info_route():
    """Récupère les informations système"""
    return get_system_info()

@router.get("/status")
async def get_status_route():
    """Récupère l'état des services"""
    try:
        # Vérification de l'état du serveur
        server_status = "ok"
        
        # Vérification de l'état du scraping (simple vérification d'existence)
        # Dans une implémentation réelle, vérifiez l'état effectif du service
        scraping_status = "ready"
        
        # Vérification de la connexion Qdrant
        try:
            # Test simple de connexion à Qdrant en listant les collections
            collections = await asyncio.to_thread(lambda: qdrant.client.get_collections())
            qdrant_status = "connected" if collections else "not_connected"
        except Exception as e:
            qdrant_status = "error"
            logger.error(f"Erreur de vérification Qdrant: {str(e)}")
        
        return {
            "server_status": server_status,
            "scraping_status": scraping_status,
            "qdrant_status": qdrant_status
        }
    except Exception as e:
        return {
            "server_status": "error",
            "scraping_status": "error",
            "qdrant_status": "error",
            "error": str(e)
        }

@router.get("/", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """
    Redirige vers le site statique d'administration sur Render
    """
    return HTMLResponse(
        content='<script>window.location.href = "https://bioforce-admin.onrender.com";</script>', 
        status_code=200
    )

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
        # Vérification explicite de la connexion Qdrant avant de tenter d'obtenir les statistiques
        if not qdrant.client:
            logger.error("Client Qdrant non initialisé - Tentative de reconnexion...")
            # Tentative de reconnexion
            try:
                qdrant.client = QdrantConnector().client
                if not qdrant.client:
                    return {
                        "status": "error",
                        "message": "Impossible de se connecter à Qdrant",
                        "details": {
                            "url": qdrant.url,
                            "collection": qdrant.collection_name
                        }
                    }
            except Exception as reconnect_error:
                logger.error(f"Erreur lors de la tentative de reconnexion à Qdrant: {reconnect_error}")
                return {
                    "status": "error",
                    "message": f"Erreur de reconnexion à Qdrant: {str(reconnect_error)}",
                    "details": {
                        "url": qdrant.url,
                        "collection": qdrant.collection_name
                    }
                }
        
        # Test de connexion avec une opération simple
        try:
            # Vérifier que la collection existe
            collection_exists = await asyncio.create_task(qdrant.ensure_collection())
            if not collection_exists:
                return {
                    "status": "error",
                    "message": f"La collection {qdrant.collection_name} n'existe pas ou ne peut pas être créée",
                    "details": {
                        "url": qdrant.url,
                        "collection": qdrant.collection_name
                    }
                }
        except Exception as collection_error:
            logger.error(f"Erreur lors de la vérification de la collection: {collection_error}")
            return {
                "status": "error",
                "message": f"Erreur d'accès à la collection: {str(collection_error)}",
                "details": {
                    "url": qdrant.url,
                    "collection": qdrant.collection_name
                }
            }
        
        # Récupération des statistiques
        stats = await qdrant.get_stats()
        
        # Ajout d'informations sur la connexion
        connection_info = {
            "url": qdrant.url,
            "collection": qdrant.collection_name,
            "is_connected": qdrant.client is not None,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        return {
            "status": "success",
            "connection": connection_info,
            "data": stats
        }
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des statistiques Qdrant: {e}")
        return {
            "status": "error",
            "message": str(e),
            "details": {
                "url": getattr(qdrant, "url", "Non disponible"),
                "collection": getattr(qdrant, "collection_name", "Non disponible")
            }
        }

# Chemin du fichier de stockage des templates d'email
EMAIL_TEMPLATES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'email_templates.json')

# Templates d'email par défaut
DEFAULT_EMAIL_TEMPLATES = {
    "contact": {
        "type": "contact",
        "subject": "Bioforce - Accusé de réception de votre message",
        "content": """<p>Bonjour {{prenom}} {{nom}},</p>
<p>Nous avons bien reçu votre message et vous remercions de nous avoir contactés.</p>
<p>Un membre de notre équipe vous répondra dans les plus brefs délais.</p>
<p>Cordialement,</p>
<p>L'équipe Bioforce</p>""",
        "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    },
    "registration": {
        "type": "registration",
        "subject": "Bioforce - Confirmation de votre inscription",
        "content": """<p>Bonjour {{prenom}} {{nom}},</p>
<p>Nous vous confirmons votre inscription sur notre plateforme.</p>
<p>Pour activer votre compte, veuillez cliquer sur le lien suivant : <a href="{{lien_confirmation}}">Confirmer mon compte</a></p>
<p>Cordialement,</p>
<p>L'équipe Bioforce</p>""",
        "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    },
    "welcome": {
        "type": "welcome",
        "subject": "Bioforce - Bienvenue !",
        "content": """<p>Bonjour {{prenom}} {{nom}},</p>
<p>Nous sommes ravis de vous accueillir sur notre plateforme.</p>
<p>N'hésitez pas à explorer les différentes fonctionnalités disponibles et à nous contacter si vous avez des questions.</p>
<p>Cordialement,</p>
<p>L'équipe Bioforce</p>""",
        "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    },
    "newsletter": {
        "type": "newsletter",
        "subject": "Bioforce - Newsletter du {{date}}",
        "content": """<p>Bonjour {{prenom}} {{nom}},</p>
<p>Voici les dernières actualités de Bioforce :</p>
<ul>
  <li>Nouvelle fonctionnalité : chatbot amélioré</li>
  <li>Mises à jour de notre base de connaissances</li>
  <li>Événements à venir</li>
</ul>
<p>Cordialement,</p>
<p>L'équipe Bioforce</p>""",
        "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
}

def get_email_templates() -> Dict[str, EmailTemplate]:
    """
    Récupère tous les templates d'email depuis le fichier de stockage.
    Si le fichier n'existe pas, utilise les templates par défaut.
    """
    try:
        if not os.path.exists(EMAIL_TEMPLATES_FILE):
            # Créer le fichier avec les templates par défaut
            with open(EMAIL_TEMPLATES_FILE, 'w', encoding='utf-8') as f:
                json.dump(DEFAULT_EMAIL_TEMPLATES, f, ensure_ascii=False, indent=4)
            return DEFAULT_EMAIL_TEMPLATES
        
        with open(EMAIL_TEMPLATES_FILE, 'r', encoding='utf-8') as f:
            templates = json.load(f)
            return templates
    except Exception as e:
        logger.error(f"Erreur lors de la lecture des templates d'email: {str(e)}")
        return DEFAULT_EMAIL_TEMPLATES

def save_email_template(template: EmailTemplate) -> bool:
    """
    Enregistre un template d'email dans le fichier de stockage.
    """
    try:
        templates = get_email_templates()
        template_dict = template.dict()
        template_dict["last_updated"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        templates[template.type] = template_dict
        
        with open(EMAIL_TEMPLATES_FILE, 'w', encoding='utf-8') as f:
            json.dump(templates, f, ensure_ascii=False, indent=4)
        
        return True
    except Exception as e:
        logger.error(f"Erreur lors de l'enregistrement du template d'email: {str(e)}")
        return False

@router.get("/email-template")
async def get_email_template_route(type: str = Query(..., description="Type de template à récupérer")):
    """
    Récupère un template d'email spécifique
    """
    try:
        templates = get_email_templates()
        
        if type not in templates:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": f"Template de type '{type}' non trouvé"}
            )
        
        return JSONResponse(
            status_code=200,
            content=templates[type]
        )
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du template d'email: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Erreur serveur: {str(e)}"}
        )

@router.post("/email-template")
async def save_email_template_route(template: EmailTemplate):
    """
    Enregistre ou met à jour un template d'email
    """
    try:
        success = save_email_template(template)
        
        if not success:
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": "Erreur lors de l'enregistrement du template"}
            )
        
        return JSONResponse(
            status_code=200,
            content={"success": True, "message": f"Template '{template.type}' enregistré avec succès"}
        )
    except Exception as e:
        logger.error(f"Erreur lors de l'enregistrement du template d'email: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Erreur serveur: {str(e)}"}
        )
