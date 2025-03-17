"""
Module de planification des tâches automatiques
"""
import asyncio
import logging
import os
import signal
import sys
import time
from datetime import datetime
from typing import Dict, Any, Callable, Coroutine, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bioforce_scraper.config import (FAQ_UPDATE_CRON, FULL_SITE_UPDATE_CRON, LOG_FILE, 
                   REMINDER_INTERVAL_MINUTES, SCHEDULER_ENABLED)
from bioforce_scraper.utils.logger import setup_logger

# Configuration du logger
logger = setup_logger(__name__, LOG_FILE)

class BioforceScheduler:
    """
    Planificateur de tâches pour le scraper Bioforce
    """
    
    def __init__(self):
        """
        Initialise le planificateur
        """
        self.scheduler = AsyncIOScheduler()
        self.running = False
        self.current_jobs = {}
    
    async def faq_update_job(self):
        """
        Tâche de mise à jour de la FAQ
        """
        logger.info("Démarrage de la tâche planifiée: Mise à jour de la FAQ")
        try:
            from bioforce_scraper.faq_scraper import FAQScraper
            scraper = FAQScraper()
            results = await scraper.run()
            
            if "error" in results:
                logger.error(f"Erreur lors de la mise à jour de la FAQ: {results['error']}")
                return False
            
            logger.info(f"Mise à jour de la FAQ terminée: {len(results['new_items'])} nouveaux éléments, "
                       f"{len(results['updated_items'])} éléments mis à jour")
            return True
            
        except Exception as e:
            logger.error(f"Exception lors de la mise à jour de la FAQ: {e}")
            return False
    
    async def full_site_update_job(self):
        """
        Tâche de mise à jour complète du site
        """
        logger.info("Démarrage de la tâche planifiée: Mise à jour complète du site")
        try:
            from bioforce_scraper.main import BioforceScraperMain
            scraper = BioforceScraperMain(incremental=True)
            result = await scraper.run()
            
            logger.info(f"Mise à jour du site terminée: {len(result.get('new_content', []))} nouveaux éléments, "
                       f"{len(result.get('updated_content', []))} éléments mis à jour")
            return True
            
        except Exception as e:
            logger.error(f"Exception lors de la mise à jour du site: {e}")
            return False
    
    async def reminder_job(self):
        """
        Tâche de rappel pour les utilisateurs
        """
        logger.info("Envoi des rappels aux utilisateurs")
        try:
            from bioforce_scraper.utils.reminder_service import send_reminders
            result = await send_reminders()
            
            return result
            
        except Exception as e:
            logger.error(f"Exception lors de l'envoi des rappels: {e}")
            return False
    
    def schedule_faq_update(self, cron_expression: str = FAQ_UPDATE_CRON):
        """
        Planifie la mise à jour de la FAQ
        
        Args:
            cron_expression: Expression cron pour la planification
        """
        job = self.scheduler.add_job(
            self.faq_update_job,
            CronTrigger.from_crontab(cron_expression),
            id="faq_update",
            replace_existing=True
        )
        
        self.current_jobs["faq_update"] = job
        logger.info(f"Tâche de mise à jour de la FAQ planifiée: {cron_expression}")
    
    def schedule_full_site_update(self, cron_expression: str = FULL_SITE_UPDATE_CRON):
        """
        Planifie la mise à jour complète du site
        
        Args:
            cron_expression: Expression cron pour la planification
        """
        job = self.scheduler.add_job(
            self.full_site_update_job,
            CronTrigger.from_crontab(cron_expression),
            id="full_site_update",
            replace_existing=True
        )
        
        self.current_jobs["full_site_update"] = job
        logger.info(f"Tâche de mise à jour complète du site planifiée: {cron_expression}")
    
    def schedule_reminder(self, interval_minutes: int = REMINDER_INTERVAL_MINUTES):
        """
        Planifie l'envoi de rappels aux utilisateurs
        
        Args:
            interval_minutes: Intervalle en minutes entre les rappels
        """
        job = self.scheduler.add_job(
            self.reminder_job,
            "interval",
            minutes=interval_minutes,
            id="reminder",
            replace_existing=True
        )
        
        self.current_jobs["reminder"] = job
        logger.info(f"Tâche d'envoi de rappels planifiée: toutes les {interval_minutes} minutes")
    
    def start(self):
        """
        Démarre le planificateur
        """
        if not SCHEDULER_ENABLED:
            logger.info("Planificateur désactivé dans la configuration")
            return
        
        try:
            # Planifier les tâches
            self.schedule_faq_update()
            self.schedule_full_site_update()
            self.schedule_reminder()
            
            # Démarrer le planificateur
            self.scheduler.start()
            self.running = True
            
            logger.info("Planificateur démarré")
            
            # Configuration des gestionnaires de signaux pour l'arrêt propre
            def handle_exit_signal(sig, frame):
                logger.info(f"Signal reçu: {sig}")
                self.stop()
                sys.exit(0)
            
            signal.signal(signal.SIGINT, handle_exit_signal)
            signal.signal(signal.SIGTERM, handle_exit_signal)
            
        except Exception as e:
            logger.error(f"Erreur lors du démarrage du planificateur: {e}")
    
    def stop(self):
        """
        Arrête le planificateur
        """
        if self.running:
            self.scheduler.shutdown()
            self.running = False
            logger.info("Planificateur arrêté")
    
    def get_next_run_times(self) -> Dict[str, Any]:
        """
        Récupère les prochaines exécutions planifiées
        
        Returns:
            Dictionnaire avec les noms des tâches et leurs prochaines exécutions
        """
        next_runs = {}
        
        for job_id, job in self.current_jobs.items():
            next_run = job.next_run_time
            next_runs[job_id] = next_run.isoformat() if next_run else None
        
        return next_runs
    
    def run_job_now(self, job_id: str) -> bool:
        """
        Exécute immédiatement une tâche planifiée
        
        Args:
            job_id: Identifiant de la tâche
            
        Returns:
            True si la tâche a été démarrée, False sinon
        """
        if job_id not in self.current_jobs:
            logger.error(f"Tâche inconnue: {job_id}")
            return False
        
        try:
            # Exécuter la tâche immédiatement
            self.scheduler.add_job(
                getattr(self, f"{job_id}_job"),
                id=f"{job_id}_immediate_{int(time.time())}",
                next_run_time=datetime.now()
            )
            
            logger.info(f"Tâche {job_id} démarrée manuellement")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors du démarrage manuel de la tâche {job_id}: {e}")
            return False

# Module de service pour FastAPI
class SchedulerService:
    """
    Service de planification pour l'intégration avec FastAPI
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SchedulerService, cls).__new__(cls)
            cls._instance.scheduler = BioforceScheduler()
        return cls._instance
    
    def start_scheduler(self):
        """
        Démarre le planificateur
        """
        self.scheduler.start()
    
    def stop_scheduler(self):
        """
        Arrête le planificateur
        """
        self.scheduler.stop()
    
    def get_job_status(self) -> Dict[str, Any]:
        """
        Récupère le statut des tâches planifiées
        
        Returns:
            Dictionnaire avec les informations de statut
        """
        return {
            "running": self.scheduler.running,
            "next_runs": self.scheduler.get_next_run_times()
        }
    
    def run_job(self, job_id: str) -> bool:
        """
        Exécute immédiatement une tâche planifiée
        
        Args:
            job_id: Identifiant de la tâche
            
        Returns:
            True si la tâche a été démarrée, False sinon
        """
        return self.scheduler.run_job_now(job_id)

# Exemple d'utilisation autonome
async def main():
    """
    Fonction principale
    """
    scheduler = BioforceScheduler()
    scheduler.start()
    
    # Exécuter immédiatement la mise à jour de la FAQ
    await scheduler.faq_update_job()
    
    try:
        # Maintenir le programme en vie
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        scheduler.stop()

if __name__ == "__main__":
    asyncio.run(main())
