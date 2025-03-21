"""
API FastAPI pour le chatbot Bioforce
"""
# Imports système de base pour configurer l'environnement
import os
import sys
import pathlib
from datetime import datetime
from typing import Optional

# Ajout du répertoire parent au sys.path (AVANT les imports internes)
parent_dir = str(pathlib.Path(__file__).parent.parent.parent)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Imports tiers
import uvicorn  # noqa: E402
from fastapi import FastAPI, BackgroundTasks  # noqa: E402
from fastapi.responses import JSONResponse, HTMLResponse  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

# Imports internes (après l'ajout au sys.path)
from bioforce_scraper.utils.logger import setup_logger  # noqa: E402
from bioforce_scraper.api.models import QueryRequest, ScrapeRequest  # noqa: E402
from bioforce_scraper.utils.qdrant_connector import QdrantConnector  # noqa: E402
from bioforce_scraper.utils.embedding_generator import generate_embeddings  # noqa: E402
from bioforce_scraper.config import (  # noqa: E402
    API_VERSION, LOG_FILE, API_HOST, API_PORT, 
    SCHEDULER_ENABLED, REMINDER_ENABLED
)
from bioforce_scraper.faq_scraper import FAQScraper  # noqa: E402
from bioforce_scraper.scheduler import SchedulerService  # noqa: E402
from bioforce_scraper.api.admin import router as admin_router  # noqa: E402
from bioforce_scraper.utils.reminder_service import ReminderService  # noqa: E402
from bioforce_scraper.main import BioforceScraperMain  # noqa: E402
from bioforce_scraper.api.system_status import get_system_status, generate_status_html  # noqa: E402

# Configuration du logger
logger = setup_logger(__name__, LOG_FILE)

# Création de l'application FastAPI
app = FastAPI(
    title="Bioforce Chatbot API",
    description="API pour le chatbot Bioforce",
    version=API_VERSION
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montage des routes admin
app.include_router(admin_router)

# Montage des fichiers statiques avec un chemin absolu
current_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(current_dir, "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")
os.makedirs(static_dir, exist_ok=True)

# Services
scheduler_service = SchedulerService()
reminder_service = ReminderService()  # Instance du service de rappels
qdrant_faq = QdrantConnector(is_full_site=False)  # Collection FAQ
qdrant_full = QdrantConnector(is_full_site=True)  # Collection site complet

# Définir ici la classe ReminderRequest car elle n'est pas importée
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
        "api_version": API_VERSION
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
        
        # Déterminer quelle collection interroger
        search_type = request.search_type.lower() if request.search_type else "auto"
        
        # Mots-clés associés aux questions de candidature/admission
        faq_keywords = [
            "admission", "candidature", "formation", "logistique", "prérequis", 
            "diplôme", "financement", "bourse", "frais", "étudiant", "élève",
            "inscription", "cours", "date", "programme", "certificat", "stage"
        ]
        
        if search_type == "auto":
            # Détecter automatiquement si la question concerne la candidature (FAQ)
            query_lower = request.query.lower()
            is_faq_related = any(keyword in query_lower for keyword in faq_keywords)
            
            # Si la question semble liée à la FAQ, utiliser cette collection en priorité
            if is_faq_related:
                search_type = "faq"
            else:
                search_type = "site"
        
        # Effectuer la recherche dans la collection appropriée
        if search_type == "faq":
            search_results = qdrant_faq.search(
                query_vector=query_embedding,
                limit=max(20, request.max_results),  
                filter_conditions=filters
            )
            # Filtrer les résultats avec un score trop faible
            search_results = [r for r in search_results if r["score"] > 0.001]
            # Trier explicitement par score
            search_results = sorted(search_results, key=lambda x: x["score"], reverse=True)
            collection_used = "FAQ (BIOFORCE)"
        else:  # "site"
            search_results = qdrant_full.search(
                query_vector=query_embedding,
                limit=max(20, request.max_results),  
                filter_conditions=filters
            )
            # Filtrer les résultats avec un score trop faible
            search_results = [r for r in search_results if r["score"] > 0.001]
            # Trier explicitement par score
            search_results = sorted(search_results, key=lambda x: x["score"], reverse=True)
            collection_used = "Site complet (BIOFORCE_ALL)"
            
            # Si on ne trouve pas de résultats pertinents dans le site complet, 
            # essayer aussi la FAQ comme sauvegarde
            if not search_results or search_results[0]["score"] < 0.7:
                backup_results = qdrant_faq.search(
                    query_vector=query_embedding,
                    limit=max(20, request.max_results),  
                    filter_conditions=filters
                )
                
                # Filtrer les résultats avec un score trop faible
                backup_results = [r for r in backup_results if r["score"] > 0.001]
                # Trier explicitement par score
                backup_results = sorted(backup_results, key=lambda x: x["score"], reverse=True)
                
                # Ajouter des résultats de la FAQ s'ils sont pertinents
                if backup_results and backup_results[0]["score"] > 0.7:
                    search_results = search_results + backup_results
                    collection_used = "Site complet + FAQ (BIOFORCE_ALL + BIOFORCE)"
        
        # Logger la requête pour analyse ultérieure
        logger.info(f"Requête: '{request.query}' - Collection: {collection_used} - Résultats: {len(search_results)}")
        
        return {
            "status": "success",
            "query": request.query,
            "results": search_results,
            "collection": collection_used,
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

@app.get("/qdrant-stats")
async def get_qdrant_stats():
    """Endpoint pour récupérer les statistiques de Qdrant"""
    try:
        # Obtenir les statistiques des deux collections
        faq_stats = qdrant_faq.get_stats()
        full_stats = qdrant_full.get_stats()
        
        return {
            "status": "success",
            "faq_collection": faq_stats,
            "full_site_collection": full_stats,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des statistiques Qdrant: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

@app.get("/system-status")
async def system_status_route():
    """Endpoint pour obtenir l'état du système"""
    try:
        status_data = await get_system_status()
        return status_data
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de l'état du système: {e}")
        return JSONResponse(
            status_code=500, 
            content={"status": "error", "message": str(e)}
        )

@app.get("/system-status-widget", response_class=HTMLResponse)
async def system_status_widget_route():
    """Endpoint pour obtenir un widget HTML montrant l'état du système"""
    try:
        status_data = await get_system_status()
        html_content = generate_status_html(status_data)
        return html_content
    except Exception as e:
        logger.error(f"Erreur lors de la génération du widget d'état: {e}")
        return f"""
        <div style="color: red; padding: 20px; text-align: center;">
            <h3>Erreur de chargement du statut</h3>
            <p>{str(e)}</p>
        </div>
        """

@app.post("/chat")
async def chat(request: dict):
    """Endpoint pour le chat avec le chatbot"""
    try:
        # Récupérer les informations de la requête
        user_id = request.get("user_id", "anonymous")
        messages = request.get("messages", [])
        # Le contexte peut contenir des informations spécifiques à la session que nous utiliserons ultérieurement
        session_context = request.get("context", {})
        
        # Vérifier qu'il y a au moins un message
        if not messages:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Aucun message fourni"}
            )
        
        # Obtenir le dernier message de l'utilisateur
        last_message = messages[-1]["content"]
        
        # Vérifier les commandes spéciales (comme *Admin*)
        if last_message.strip() == "*Admin*":
            return {
                "status": "success",
                "message": {
                    "role": "assistant",
                    "content": "Accès à l'interface d'administration accordé. Ouverture de la page dans un nouvel onglet."
                },
                "action": "open_admin",
                "admin_url": "/admin"
            }
        
        # Créer un embedding pour la requête
        query_embedding = await generate_embeddings(last_message)
        if not query_embedding:
            raise Exception("Impossible de générer l'embedding pour la requête")
        
        # On peut utiliser le contexte pour ajuster les filtres de recherche si nécessaire
        additional_filters = session_context.get("filters", {})
        
        # Rechercher dans les deux collections (FAQ et site complet)
        faq_results = qdrant_faq.search(query_vector=query_embedding, limit=3, filter_conditions=additional_filters)
        site_results = qdrant_full.search(query_vector=query_embedding, limit=3, filter_conditions=additional_filters)
        
        # Combiner les résultats (avec priorité à la FAQ si pertinent)
        combined_results = []
        
        # Analyser si la question concerne la FAQ
        faq_keywords = [
            "admission", "candidature", "formation", "logistique", "prérequis", 
            "diplôme", "financement", "bourse", "frais", "étudiant", "élève",
            "inscription", "cours", "date", "programme", "certificat", "stage"
        ]
        
        is_faq_related = any(keyword in last_message.lower() for keyword in faq_keywords)
        
        # Prioriser selon le type de question
        if is_faq_related and faq_results and faq_results[0]["score"] > 0.7:
            # Question FAQ, prioriser ces résultats
            combined_results = faq_results + site_results
        elif site_results and site_results[0]["score"] > 0.7:
            # Question site, prioriser ces résultats
            combined_results = site_results + faq_results
        else:
            # Pas de préférence claire, mélanger selon les scores
            combined_results = sorted(faq_results + site_results, key=lambda x: x["score"], reverse=True)
        
        # Générer la réponse
        bot_response = ""
        references = []
        
        # Vérifier si nous avons des résultats pertinents (score > 0.7)
        has_relevant_results = combined_results and combined_results[0]["score"] > 0.7
        
        if has_relevant_results:
            # Utiliser le résultat le plus pertinent
            top_result = combined_results[0]
            bot_response = top_result["content"]
            
            # Ajouter les références
            for result in combined_results[:3]:  # Limiter à 3 références
                if result["score"] > 0.6:  # Seuil de pertinence pour les références
                    references.append({
                        "title": result.get("title", ""),
                        "url": result.get("source_url", ""),
                        "score": result["score"]
                    })
        else:
            # Pas de résultat pertinent trouvé, reformuler la question et fournir la meilleure réponse
            best_result = combined_results[0] if combined_results else None
            
            if best_result:
                # Construire une réponse qui reconnaît l'absence de correspondance exacte
                bot_response = (
                    f"Je n'ai pas trouvé de réponse exacte à votre question '{last_message}'. "
                    f"Cependant, voici l'information la plus proche dont je dispose :\n\n"
                    f"{best_result['content']}\n\n"
                    f"Cette réponse traite de '{best_result.get('title', 'ce sujet')}' qui pourrait être lié à votre question."
                )
                
                # Ajouter la référence
                references.append({
                    "title": best_result.get("title", ""),
                    "url": best_result.get("source_url", ""),
                    "score": best_result["score"]
                })
            else:
                # Aucun résultat du tout
                bot_response = (
                    f"Je n'ai pas trouvé d'information sur votre question '{last_message}'. "
                    f"Je vous invite à reformuler votre question ou à contacter directement notre équipe "
                    f"pour obtenir une réponse personnalisée."
                )
        
        # Logger la requête et la réponse
        logger.info(f"Chat - User: {user_id}, Question: '{last_message}'")
        
        # Retourner la réponse
        return {
            "status": "success",
            "message": {
                "role": "assistant",
                "content": bot_response
            },
            "references": references,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Erreur lors du traitement du chat: {e}")
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
        scraper = BioforceScraperMain(incremental=not force_update)
        await scraper.run()
    except Exception as e:
        logger.error(f"Erreur dans la tâche d'arrière-plan de scraping complet: {e}")

@app.on_event("startup")
async def startup_event():
    """Événement de démarrage de l'application"""
    logger.info("Démarrage de l'API Bioforce")
    
    # S'assurer que la collection Qdrant existe
    qdrant_faq.ensure_collection()
    qdrant_full.ensure_collection()
    
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
