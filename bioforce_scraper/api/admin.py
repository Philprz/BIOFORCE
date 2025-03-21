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
import traceback

# Ajout du répertoire parent au path pour les importations
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from bioforce_scraper.config import VERSION, GITHUB_REPO, VECTOR_SIZE
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
    """Récupère l'état des services avec informations détaillées"""
    try:
        # Structure pour les résultats avec un format uniforme
        results = {
            "server": {
                "status": "ok",
                "message": "Serveur opérationnel",
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            },
            "scraping": {
                "status": "ok",
                "message": "Service de scraping prêt"
            },
            "qdrant": {
                "status": "unknown",
                "message": "Statut de Qdrant inconnu",
                "details": {}
            }
        }
        
        # Vérification détaillée de la connexion Qdrant
        try:
            # Capture des informations détaillées de connexion
            qdrant_details = {
                "host": getattr(qdrant.client, "_host", "Non disponible"),
                "port": getattr(qdrant.client, "_port", "Non disponible"),
                "collection": getattr(qdrant, "collection_name", "Non disponible"),
                "timeout": getattr(qdrant.client, "_timeout", "Non disponible"),
                "api_key_provided": bool(getattr(qdrant.client, "_api_key", None)),
                "connection_attempt_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Test de connexion à Qdrant en listant les collections
            try:
                # Vérification simple d'abord (liste des collections)
                collections_list = await asyncio.to_thread(lambda: qdrant.client.get_collections())
                qdrant_details["collections_found"] = len(collections_list.collections)
                qdrant_details["collections_list"] = [c.name for c in collections_list.collections]
                
                # Vérification spécifique de la collection BIOFORCE
                collection_info = await asyncio.to_thread(lambda: qdrant.client.get_collection(qdrant.collection_name))
                qdrant_details["collection_info"] = {
                    "vectors_count": collection_info.vectors_count,
                    "points_count": collection_info.points_count,
                    "segments_count": collection_info.segments_count,
                    "status": collection_info.status
                }
                
                # Tout va bien
                results["qdrant"]["status"] = "ok"
                results["qdrant"]["message"] = "Connexion à Qdrant établie avec succès"
                
            except Exception as collection_error:
                # La connexion fonctionne mais problème avec les collections
                logger.warning(f"Erreur lors de la vérification des collections Qdrant: {str(collection_error)}")
                qdrant_details["collection_error"] = str(collection_error)
                results["qdrant"]["status"] = "warning"
                results["qdrant"]["message"] = f"Connexion à Qdrant établie mais erreur lors de l'accès aux collections: {str(collection_error)}"
            
            # Ajout des détails à la réponse
            results["qdrant"]["details"] = qdrant_details
            
        except Exception as e:
            # Erreur de connexion à Qdrant
            logger.error(f"Erreur de connexion à Qdrant: {str(e)}")
            results["qdrant"]["status"] = "error"
            results["qdrant"]["message"] = f"Erreur de connexion à Qdrant: {str(e)}"
            results["qdrant"]["details"] = {
                "error": str(e),
                "error_type": type(e).__name__,
                "host": getattr(qdrant, "url", "Non disponible"),
                "port": getattr(qdrant, "collection_name", "Non disponible"),
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        
        return results
        
    except Exception as e:
        # Erreur générale du serveur
        logger.error(f"Erreur lors de la vérification de l'état des services: {str(e)}")
        return {
            "server": {
                "status": "error",
                "message": f"Erreur serveur: {str(e)}",
                "error_type": type(e).__name__
            },
            "scraping": {"status": "unknown", "message": "Statut inconnu en raison d'une erreur serveur"},
            "qdrant": {"status": "unknown", "message": "Statut inconnu en raison d'une erreur serveur"}
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
    """Route pour obtenir les statistiques détaillées de Qdrant avec diagnostics avancés"""
    try:
        # Structure initiale de la réponse
        response = {
            "status": "pending",
            "message": "Analyse de la connexion Qdrant en cours",
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "connection": {
                "url": getattr(qdrant, "url", "Non disponible"),
                "collection": getattr(qdrant, "collection_name", "Non disponible"),
                "client_initialized": qdrant.client is not None,
                "diagnostics": {}
            },
            "data": None,
            "debug_logs": []
        }
        
        # Fonction pour ajouter des logs de debug
        def add_debug_log(message, level="info", data=None):
            log_entry = {
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                "level": level,
                "message": message
            }
            if data:
                log_entry["data"] = data
                
            response["debug_logs"].append(log_entry)
            
            # Log aussi dans les logs système selon le niveau
            if level == "error":
                logger.error(message)
            elif level == "warning":
                logger.warning(message)
            else:
                logger.info(message)
                
            return log_entry
            
        # Phase 1: Vérification de l'initialisation du client
        add_debug_log("Vérification de l'initialisation du client Qdrant")
        
        if not qdrant.client:
            add_debug_log("Client Qdrant non initialisé - Tentative de reconnexion", "warning")
            
            # Tentative de reconnexion
            try:
                # Capture l'état avant la reconnexion
                response["connection"]["diagnostics"]["pre_reconnect"] = {
                    "client_initialized": qdrant.client is not None,
                    "url": getattr(qdrant, "url", "Non disponible"),
                    "client_attributes": {
                        attr: getattr(qdrant, attr, "Non disponible") 
                        for attr in ["collection_name", "dim", "metric", "distance"]
                    }
                }
                
                # Tentative de reconnexion
                add_debug_log("Initialisation d'un nouveau connecteur Qdrant")
                qdrant.client = QdrantConnector().client
                
                # Vérifie si la reconnexion a réussi
                if not qdrant.client:
                    add_debug_log("Échec de reconnexion à Qdrant - client toujours None", "error")
                    response["status"] = "error"
                    response["message"] = "Impossible de se connecter à Qdrant - client non initialisé après reconnexion"
                    return response
                    
                add_debug_log("Reconnexion à Qdrant réussie", "info", {
                    "host": getattr(qdrant.client, "_host", "Non disponible"),
                    "port": getattr(qdrant.client, "_port", "Non disponible")
                })
                
                # Mise à jour des informations de connexion
                response["connection"]["client_initialized"] = True
                
            except Exception as reconnect_error:
                error_info = {
                    "error_type": type(reconnect_error).__name__,
                    "error_message": str(reconnect_error),
                    "traceback": traceback.format_exc()
                }
                
                add_debug_log(f"Erreur lors de la tentative de reconnexion à Qdrant: {reconnect_error}", "error", error_info)
                
                response["status"] = "error"
                response["message"] = f"Erreur de reconnexion à Qdrant: {str(reconnect_error)}"
                response["connection"]["diagnostics"]["reconnect_error"] = error_info
                return response
        else:
            add_debug_log("Client Qdrant déjà initialisé", "info", {
                "host": getattr(qdrant.client, "_host", "Non disponible"),
                "port": getattr(qdrant.client, "_port", "Non disponible"),
                "api_key_present": bool(getattr(qdrant.client, "_api_key", None))
            })
        
        # Phase 2: Vérification de la collection
        add_debug_log(f"Vérification de la collection '{qdrant.collection_name}'")
        
        try:
            # Test basique de connexion - récupération des collections
            add_debug_log("Récupération de la liste des collections")
            
            collections_list = await asyncio.to_thread(lambda: qdrant.client.get_collections())
            collections_names = [c.name for c in collections_list.collections]
            
            add_debug_log(f"Liste des collections récupérée avec succès: {len(collections_names)} collections", "info", {
                "collections": collections_names
            })
            
            # Vérifier si notre collection est dans la liste
            if qdrant.collection_name in collections_names:
                add_debug_log(f"Collection '{qdrant.collection_name}' trouvée dans la liste")
            else:
                add_debug_log(f"Collection '{qdrant.collection_name}' NON trouvée dans la liste - vérification si elle peut être créée", "warning")
            
            # Vérification complète que la collection existe ou peut être créée
            add_debug_log("Vérification de l'existence/création de la collection via ensure_collection()")
            collection_exists = await asyncio.create_task(qdrant.ensure_collection())
            
            if not collection_exists:
                add_debug_log(f"La collection {qdrant.collection_name} n'existe pas et n'a pas pu être créée", "error")
                response["status"] = "error"
                response["message"] = f"La collection {qdrant.collection_name} n'existe pas ou ne peut pas être créée"
                return response
                
            add_debug_log(f"Collection '{qdrant.collection_name}' vérifiée et disponible")
            
            # Récupération des infos sur la collection
            add_debug_log(f"Récupération des informations sur la collection '{qdrant.collection_name}'")
            collection_info = await asyncio.to_thread(lambda: qdrant.client.get_collection(qdrant.collection_name))
            
            response["connection"]["diagnostics"]["collection_info"] = {
                "vectors_count": collection_info.vectors_count,
                "points_count": collection_info.points_count,
                "segments_count": collection_info.segments_count,
                "status": collection_info.status,
                "config": {
                    "params": {
                        "vectors": {
                            "size": collection_info.config.params.vectors.size,
                            "distance": str(collection_info.config.params.vectors.distance),
                        }
                    }
                }
            }
            
            add_debug_log(f"Informations de collection récupérées: {collection_info.points_count} points", "info", 
                          response["connection"]["diagnostics"]["collection_info"])
                
        except Exception as collection_error:
            error_info = {
                "error_type": type(collection_error).__name__,
                "error_message": str(collection_error),
                "traceback": traceback.format_exc()
            }
            
            add_debug_log(f"Erreur lors de la vérification de la collection: {collection_error}", "error", error_info)
            
            response["status"] = "error"
            response["message"] = f"Erreur d'accès à la collection: {str(collection_error)}"
            response["connection"]["diagnostics"]["collection_error"] = error_info
            return response
        
        # Phase 3: Récupération des statistiques
        add_debug_log("Récupération des statistiques via qdrant.get_stats()")
        
        try:
            # Test de recherche simple pour vérifier la disponibilité complète
            add_debug_log("Test de recherche simple pour vérifier la disponibilité complète")
            
            # Requête de recherche simple
            test_query_vector = [0.0] * VECTOR_SIZE  # Vecteur de test (tous zéros)
            test_search = await qdrant.search(
                query_vector=test_query_vector,
                limit=1
            )
            
            add_debug_log(f"Test de recherche réussi - {len(test_search)} résultats retournés", "info", {
                "results_count": len(test_search),
                "has_valid_results": bool(test_search)
            })
            
            # Récupération des statistiques complètes
            stats = await qdrant.get_stats()
            add_debug_log("Statistiques récupérées avec succès")
            
            # Mise à jour de la réponse
            response["status"] = "success"
            response["message"] = "Connexion à Qdrant établie et fonctionnelle"
            response["data"] = stats
            
            # Infos de connexion détaillées
            response["connection"].update({
                "is_connected": True,
                "url": qdrant.url,
                "collection": qdrant.collection_name,
                "timestamp": datetime.datetime.now().isoformat()
            })
            
            return response
            
        except Exception as stats_error:
            error_info = {
                "error_type": type(stats_error).__name__,
                "error_message": str(stats_error),
                "traceback": traceback.format_exc()
            }
            
            add_debug_log(f"Erreur lors de la récupération des statistiques: {stats_error}", "error", error_info)
            
            response["status"] = "error"
            response["message"] = f"Erreur lors de la récupération des statistiques: {str(stats_error)}"
            response["connection"]["diagnostics"]["stats_error"] = error_info
            return response
            
    except Exception as e:
        # Erreur générale non gérée
        logger.error(f"Erreur générale lors de la récupération des statistiques Qdrant: {e}")
        return {
            "status": "error",
            "message": f"Erreur générale: {str(e)}",
            "error_type": type(e).__name__,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "details": {
                "traceback": traceback.format_exc(),
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

@router.get("/status-demo")
async def get_status_demo_route():
    """
    Redirige vers la page de démonstration du statut système
    """
    return HTMLResponse(
        content="""
        <html>
            <head>
                <title>État du système (Feu tricolore)</title>
            </head>
            <body>
                <h1>État du système (Feu tricolore)</h1>
                <ul>
                    <li><a href="javascript:void(0);" onclick="loadContent('/admin/system-info')">Informations système</a></li>
                    <li><a href="javascript:void(0);" onclick="loadContent('/admin/qdrant-stats')">Statistiques Qdrant</a></li>
                    <li><a href="/static/status-demo.html" target="_blank">État du système (Feu tricolore)</a></li>
                </ul>
            </div>
        </body>
    </html>
    """, 
        status_code=200
    )

CSS_STYLES = """
.status-indicator-sidebar {
    position: fixed;
    top: 20px;
    right: 20px;
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 14px;
    background-color: #1f1f1f;
    padding: 8px 12px;
    border-radius: 5px;
    color: white;
}

.status-light-sidebar {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    display: inline-block;
}

.status-light-sidebar.green {
    background-color: #2ecc71;
    box-shadow: 0 0 5px #2ecc71;
}
.status-light-sidebar.orange {
    background-color: #f39c12;
    box-shadow: 0 0 5px #f39c12;
}
.status-light-sidebar.red {
    background-color: #e74c3c;
    box-shadow: 0 0 5px #e74c3c;
}
.status-light-sidebar.unknown {
    background-color: #95a5a6;
    box-shadow: 0 0 5px #95a5a6;
}
"""

CONTENT_SCRIPT = """
<script>
// Fonction pour charger et afficher l'état du système
function loadSystemStatus() {
    fetch('/system-status')
        .then(response => response.json())
        .then(data => {
            const statusContainer = document.getElementById('system-status-sidebar');
            if (statusContainer) {
                const statusLight = statusContainer.querySelector('.status-light-sidebar');
                const statusText = statusContainer.querySelector('.status-text');
                
                // Mettre à jour la classe et le texte
                statusLight.className = 'status-light-sidebar ' + data.overall_status;
                
                // Déterminer le message à afficher
                let statusMessage = 'Inconnu';
                switch(data.overall_status) {
                    case 'green': statusMessage = 'Opérationnel'; break;
                    case 'orange': statusMessage = 'Problèmes mineurs'; break;
                    case 'red': statusMessage = 'Problèmes majeurs'; break;
                }
                
                statusText.textContent = statusMessage;
                
                // Mettre à jour l'infobulle
                const tooltip = [];
                for (const [name, service] of Object.entries(data.services)) {
                    tooltip.push(`${service.name}: ${service.message}`);
                }
                statusContainer.title = tooltip.join('\\n');
            }
        })
        .catch(error => {
            console.error('Erreur lors de la récupération de l\'état du système:', error);
            const statusContainer = document.getElementById('system-status-sidebar');
            if (statusContainer) {
                const statusLight = statusContainer.querySelector('.status-light-sidebar');
                const statusText = statusContainer.querySelector('.status-text');
                
                statusLight.className = 'status-light-sidebar red';
                statusText.textContent = 'Erreur';
                statusContainer.title = 'Impossible de récupérer l\'état du système';
            }
        });
}

// Charger l'état du système au démarrage
document.addEventListener('DOMContentLoaded', function() {
    loadSystemStatus();
    // Rafraîchir toutes les 60 secondes
    setInterval(loadSystemStatus, 60000);
});
</script>
"""

@router.get("/system-status", response_class=HTMLResponse)
async def get_system_status_route(request: Request):
    """
    Redirige vers le site statique d'administration sur Render
    """
    return HTMLResponse(
        content="""
        <html>
            <head>
                <title>État du système</title>
                <style>
                    """ + CSS_STYLES + """
                </style>
            </head>
            <body>
                <h1>Administration Bioforce</h1>
                <h2>État du système</h2>
                <div id="system-status-sidebar" class="status-indicator-sidebar" onclick="window.open('/static/status-demo.html', '_blank')">
                    <span class="status-light-sidebar unknown"></span>
                    <span class="status-text">Chargement...</span>
                </div>
                """ + CONTENT_SCRIPT + """
            </div>
        </body>
    </html>
    """, 
        status_code=200
    )
