"""
Service de rappels et relances pour les candidats Bioforce
"""
import asyncio
import json
import logging
import os
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from string import Template
from typing import Dict, List, Any, Optional

import aiohttp
import aiosmtplib
from fastapi import FastAPI, BackgroundTasks

from bioforce_scraper.config import (LOG_FILE, FOLLOWUP_EMAIL_TEMPLATE, FOLLOWUP_EMAIL_SUBJECT,
                  FOLLOWUP_DAYS_THRESHOLD, REMINDER_MESSAGE)
from bioforce_scraper.utils.logger import setup_logger

# Configuration du logger
logger = setup_logger(__name__, LOG_FILE)

class ReminderService:
    """
    Service de gestion des rappels et relances pour les candidats
    """
    
    def __init__(self, app: Optional[FastAPI] = None, db_url: Optional[str] = None):
        """
        Initialise le service de rappels
        
        Args:
            app: Instance FastAPI (pour intégration)
            db_url: URL de la base de données des candidats
        """
        self.app = app
        self.db_url = db_url
        
        # Charger le template d'email
        self.email_template = self._load_email_template()
    
    def _load_email_template(self) -> Optional[Template]:
        """
        Charge le template d'email de relance
        
        Returns:
            Template chargé ou None en cas d'erreur
        """
        try:
            if os.path.exists(FOLLOWUP_EMAIL_TEMPLATE):
                with open(FOLLOWUP_EMAIL_TEMPLATE, 'r', encoding='utf-8') as f:
                    template_content = f.read()
                return Template(template_content)
            else:
                # Créer un template par défaut si le fichier n'existe pas
                template_content = """
                <html>
                <body>
                    <h2>Bonjour ${prenom},</h2>
                    
                    <p>Nous avons remarqué que vous avez commencé votre candidature à Bioforce il y a quelques jours, 
                    mais que celle-ci n'a pas été finalisée.</p>
                    
                    <p>Pour poursuivre votre candidature, il vous suffit de vous connecter à 
                    <a href="${portal_url}">votre espace candidat</a>.</p>
                    
                    <p>Si vous rencontrez des difficultés ou avez des questions, n'hésitez pas à utiliser notre 
                    <a href="${chatbot_url}">assistant virtuel</a> qui pourra vous aider à compléter votre dossier.</p>
                    
                    <p>L'équipe Bioforce reste à votre disposition pour toute information complémentaire.</p>
                    
                    <p>Cordialement,</p>
                    <p>L'équipe Bioforce</p>
                </body>
                </html>
                """
                
                # Créer le répertoire des templates si nécessaire
                os.makedirs(os.path.dirname(FOLLOWUP_EMAIL_TEMPLATE), exist_ok=True)
                
                # Sauvegarder le template par défaut
                with open(FOLLOWUP_EMAIL_TEMPLATE, 'w', encoding='utf-8') as f:
                    f.write(template_content)
                
                return Template(template_content)
                
        except Exception as e:
            logger.error(f"Erreur lors du chargement du template d'email: {e}")
            return None
    
    async def get_inactive_candidates(self) -> List[Dict[str, Any]]:
        """
        Récupère la liste des candidats inactifs
        
        Returns:
            Liste des candidats inactifs
        """
        # Pour l'implémentation de test, nous utilisons des données fictives
        # À remplacer par une requête à la base de données réelle
        
        inactive_candidates = [
            {
                "id": "1234",
                "email": "candidat1@example.com",
                "prenom": "Marie",
                "nom": "Dupont",
                "derniere_connexion": (datetime.now() - timedelta(days=10)).isoformat(),
                "etape_candidature": "Formulaire initial",
                "formation": "Logisticien Humanitaire"
            },
            {
                "id": "5678",
                "email": "candidat2@example.com",
                "prenom": "Jean",
                "nom": "Martin",
                "derniere_connexion": (datetime.now() - timedelta(days=8)).isoformat(),
                "etape_candidature": "Documents personnels",
                "formation": "Responsable de Projets Eau, Hygiène et Assainissement"
            }
        ]
        
        logger.info(f"Récupération de {len(inactive_candidates)} candidats inactifs")
        return inactive_candidates
    
    async def send_reminder_email(self, candidate: Dict[str, Any], 
                                background_tasks: Optional[BackgroundTasks] = None) -> bool:
        """
        Envoie un email de rappel à un candidat
        
        Args:
            candidate: Informations du candidat
            background_tasks: Tâches en arrière-plan (FastAPI)
            
        Returns:
            True si l'email a été envoyé, False sinon
        """
        if not self.email_template:
            logger.error("Template d'email non disponible")
            return False
        
        try:
            # Préparer le contenu de l'email
            portal_url = "https://candidature.bioforce.org/espace-candidat/"
            chatbot_url = "https://bioforce.org/?chatbot=open"
            
            email_content = self.email_template.substitute(
                prenom=candidate["prenom"],
                id=candidate["id"],
                portal_url=portal_url,
                chatbot_url=chatbot_url,
                formation=candidate["formation"]
            )
            
            # Créer le message
            msg = MIMEMultipart()
            msg["From"] = "noreply@bioforce.org"
            msg["To"] = candidate["email"]
            msg["Subject"] = FOLLOWUP_EMAIL_SUBJECT
            
            # Ajouter le contenu HTML
            msg.attach(MIMEText(email_content, "html"))
            
            # Dans un environnement de production, envoyez réellement l'email
            # En mode développement, nous simulons l'envoi
            
            if background_tasks:
                # En utilisant FastAPI
                background_tasks.add_task(self._send_email_async, msg, candidate["email"])
            else:
                # En mode autonome
                await self._send_email_async(msg, candidate["email"])
            
            logger.info(f"Email de relance envoyé à {candidate['email']}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi de l'email de relance: {e}")
            return False
    
    async def _send_email_async(self, msg: MIMEMultipart, recipient: str):
        """
        Envoie un email de manière asynchrone
        
        Args:
            msg: Message à envoyer
            recipient: Adresse email du destinataire
        """
        # Pour le développement, simule l'envoi
        logger.info(f"[SIMULATION] Email envoyé à {recipient}")
        
        # Pour la production, décommentez le code suivant et configurez les variables
        """
        try:
            smtp_server = os.getenv("SMTP_SERVER", "smtp.example.com")
            smtp_port = int(os.getenv("SMTP_PORT", "587"))
            smtp_user = os.getenv("SMTP_USER", "")
            smtp_password = os.getenv("SMTP_PASSWORD", "")
            
            # Envoyer l'email via aiosmtplib
            await aiosmtplib.send(
                msg,
                hostname=smtp_server,
                port=smtp_port,
                username=smtp_user,
                password=smtp_password,
                use_tls=True
            )
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi d'email: {e}")
        """
    
    async def send_chat_reminder(self, candidate: Dict[str, Any]) -> bool:
        """
        Envoie un rappel dans le chat pour un candidat actif
        
        Args:
            candidate: Informations du candidat
            
        Returns:
            True si le rappel a été envoyé, False sinon
        """
        try:
            # Pour un système réel, envoyez le rappel via un websocket ou une API
            # Ici, nous simulons l'envoi
            
            logger.info(f"Rappel chat envoyé à l'utilisateur {candidate['id']}: {REMINDER_MESSAGE}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi du rappel chat: {e}")
            return False
    
    async def process_followups(self, background_tasks: Optional[BackgroundTasks] = None) -> Dict[str, Any]:
        """
        Traite les relances pour tous les candidats inactifs
        
        Args:
            background_tasks: Tâches en arrière-plan (FastAPI)
            
        Returns:
            Résultats du traitement des relances
        """
        logger.info("Démarrage du traitement des relances")
        
        try:
            # Récupérer les candidats inactifs
            inactive_candidates = await self.get_inactive_candidates()
            
            # Résultats
            results = {
                "emails_sent": 0,
                "emails_failed": 0,
                "candidates_processed": len(inactive_candidates)
            }
            
            # Envoyer un email à chaque candidat inactif
            for candidate in inactive_candidates:
                # Vérifier si le candidat dépasse le seuil d'inactivité
                last_activity = datetime.fromisoformat(candidate["derniere_connexion"])
                days_inactive = (datetime.now() - last_activity).days
                
                if days_inactive >= FOLLOWUP_DAYS_THRESHOLD:
                    success = await self.send_reminder_email(candidate, background_tasks)
                    if success:
                        results["emails_sent"] += 1
                    else:
                        results["emails_failed"] += 1
            
            logger.info(f"Traitement des relances terminé: {results['emails_sent']} emails envoyés")
            return results
            
        except Exception as e:
            logger.error(f"Erreur lors du traitement des relances: {e}")
            return {
                "error": str(e),
                "emails_sent": 0,
                "emails_failed": 0,
                "candidates_processed": 0
            }
    
    async def send_reminders(self) -> Dict[str, Any]:
        """
        Envoie des rappels aux utilisateurs actifs
        
        Returns:
            Résultats de l'envoi des rappels
        """
        logger.info("Envoi des rappels aux utilisateurs actifs")
        
        # Pour l'implémentation de test, nous utilisons des données fictives
        # À remplacer par une requête à la base de données réelle
        
        active_candidates = [
            {
                "id": "user_session_123",
                "email": "candidat1@example.com",
                "prenom": "Marie",
                "nom": "Dupont",
                "etape_candidature": "Formulaire de motivation",
                "actif": True,
                "temps_inactif_minutes": 6
            }
        ]
        
        results = {
            "reminders_sent": 0,
            "reminders_failed": 0,
            "candidates_processed": len(active_candidates)
        }
        
        for candidate in active_candidates:
            # Vérifier si le candidat est actif mais inactif depuis un certain temps
            if candidate["actif"] and candidate["temps_inactif_minutes"] >= REMINDER_INTERVAL_MINUTES:
                success = await self.send_chat_reminder(candidate)
                if success:
                    results["reminders_sent"] += 1
                else:
                    results["reminders_failed"] += 1
        
        logger.info(f"Envoi des rappels terminé: {results['reminders_sent']} rappels envoyés")
        return results

# Fonction pour l'intégration avec le scheduler
async def send_reminders() -> bool:
    """
    Fonction de rappel pour l'intégration avec le scheduler
    
    Returns:
        True si l'opération a réussi, False sinon
    """
    service = ReminderService()
    result = await service.send_reminders()
    return result["reminders_sent"] > 0

# Exemple d'utilisation autonome
async def main():
    """
    Fonction principale
    """
    service = ReminderService()
    result = await service.process_followups()
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
