"""
Module spécialisé pour le scraping de la FAQ Bioforce
"""
import asyncio
import json
import os
from datetime import datetime
from typing import Dict, List, Any

from playwright.async_api import async_playwright, Page

from bioforce_scraper.config import (DATA_DIR, FAQ_URLS, LOG_FILE, REPORTS_DIR, USER_AGENT)
from bioforce_scraper.utils.content_tracker import ContentTracker
from bioforce_scraper.utils.language_detector import detect_language
from bioforce_scraper.utils.logger import setup_logger
from bioforce_scraper.utils.embeddings import generate_embeddings
from bioforce_scraper.utils.qdrant_connector import QdrantConnector

# Configuration du logger
logger = setup_logger(__name__, LOG_FILE)

class FAQScraper:
    """
    Scraper spécialisé pour la FAQ Bioforce
    """
    
    def __init__(self, force_update=False):
        """
        Initialise le scraper de FAQ
        
        Args:
            force_update: Force la mise à jour même pour le contenu inchangé
        """
        self.visited_urls = set()
        self.force_update = force_update
        self.content_tracker = ContentTracker()
        self.new_faq_items = []
        self.updated_faq_items = []
        self.unchanged_faq_items = []
        self.browser = None
        self.context = None
        self.page = None
        self.qdrant = QdrantConnector(is_full_site=False)  # Collection FAQ
    
    async def initialize(self):
        """
        Initialise le navigateur et la page Playwright
        """
        logger.info("Initialisation du scraper de FAQ")
        
        try:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(headless=True)
            self.context = await self.browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1280, "height": 800}
            )
            self.page = await self.context.new_page()
            
            # S'assurer que la collection Qdrant existe
            self.qdrant.ensure_collection()
            
            return True
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation du scraper: {e}")
            return False
    
    async def close(self):
        """
        Ferme le navigateur et les ressources associées
        """
        if self.browser:
            await self.browser.close()
            logger.info("Navigateur fermé")
    
    async def extract_faq_items(self, page: Page) -> List[Dict[str, Any]]:
        """
        Extrait tous les éléments de FAQ depuis la page
        
        Args:
            page: Page Playwright
            
        Returns:
            Liste des éléments de FAQ extraits
        """
        logger.info("Extraction des éléments de FAQ")
        
        try:
            # Attendre que les éléments de FAQ soient chargés
            await page.wait_for_selector(".accordion-item", timeout=30000)
            
            # Extraire les catégories de FAQ
            categories = await page.evaluate("""
                () => {
                    const categories = [];
                    document.querySelectorAll('.accordion').forEach((accordion, index) => {
                        // Trouver le titre de la catégorie (généralement un h2 ou h3 avant l'accordéon)
                        let title = "Catégorie " + (index + 1);
                        let prevElement = accordion.previousElementSibling;
                        if (prevElement && ['H2', 'H3', 'H4'].includes(prevElement.tagName)) {
                            title = prevElement.textContent.trim();
                        }
                        
                        // Extraire les éléments de l'accordéon
                        const items = [];
                        accordion.querySelectorAll('.accordion-item').forEach(item => {
                            const questionEl = item.querySelector('.accordion-header');
                            const answerEl = item.querySelector('.accordion-body');
                            
                            if (questionEl && answerEl) {
                                const question = questionEl.textContent.trim();
                                const answerHtml = answerEl.innerHTML;
                                const answerText = answerEl.textContent.trim();
                                
                                items.push({
                                    question: question,
                                    answer: answerText,
                                    answer_html: answerHtml
                                });
                            }
                        });
                        
                        categories.push({
                            title: title,
                            items: items
                        });
                    });
                    return categories;
                }
            """)
            
            # Aplatir les catégories en une liste d'éléments FAQ
            faq_items = []
            for category in categories:
                category_title = category["title"]
                for item in category["items"]:
                    faq_items.append({
                        "category": category_title,
                        "question": item["question"],
                        "answer": item["answer"],
                        "answer_html": item["answer_html"],
                        "url": FAQ_URLS[0] + "#" + self._generate_anchor(item["question"]),
                        "language": detect_language(item["answer"]),
                        "date_extraction": datetime.now().strftime("%Y-%m-%d")
                    })
            
            logger.info(f"Extraction terminée: {len(faq_items)} éléments trouvés")
            return faq_items
            
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction des éléments de FAQ: {e}")
            return []
    
    def _generate_anchor(self, question: str) -> str:
        """
        Génère un ancre pour l'URL à partir de la question
        
        Args:
            question: Question de la FAQ
            
        Returns:
            Ancre formatée
        """
        # Simplifier la question pour créer une ancre valide
        return question.lower()\
            .replace(" ", "-")\
            .replace("?", "")\
            .replace("!", "")\
            .replace(".", "")\
            .replace(",", "")\
            .replace(":", "")\
            .replace(";", "")\
            .replace("'", "-")\
            .replace("\"", "")\
            .replace("(", "")\
            .replace(")", "")\
            .replace("à", "a")\
            .replace("é", "e")\
            .replace("è", "e")\
            .replace("ê", "e")\
            .replace("ë", "e")\
            .replace("ç", "c")\
            .replace("ù", "u")\
            .replace("û", "u")\
            .replace("ü", "u")\
            .replace("ô", "o")\
            .replace("î", "i")\
            .replace("ï", "i")[:50]
    
    async def process_faq_items(self, faq_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Traite les éléments de FAQ extraits (vérifie les nouveautés, mises à jour)
        
        Args:
            faq_items: Liste des éléments de FAQ extraits
            
        Returns:
            Statistiques de traitement
        """
        logger.info(f"Traitement de {len(faq_items)} éléments de FAQ")
        
        for item in faq_items:
            # Générer une clé unique pour cet élément
            url = item["url"]
            
            # Vérifier si cet élément est nouveau ou mis à jour
            status, is_changed, previous = self.content_tracker.check_content_status(url, item)
            
            if is_changed or self.force_update:
                # Sauvegarder l'élément
                filename = f"faq_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(self.new_faq_items) + len(self.updated_faq_items)}.json"
                file_path = os.path.join(DATA_DIR, filename)
                
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(item, f, ensure_ascii=False, indent=2)
                
                # Mettre à jour le tracker
                self.content_tracker.update_content_record(url, item, status, file_path)
                
                # Générer les embeddings et mettre à jour Qdrant
                embedding = await generate_embeddings(item["question"] + " " + item["answer"])
                if embedding:
                    content_id = f"faq_{self._generate_anchor(item['question'])}"
                    self.qdrant.upsert_document(
                        content_id, 
                        embedding, 
                        {
                            "source_url": url,
                            "title": item["question"],
                            "content": item["answer"],
                            "type": "faq",
                            "category": item["category"],
                            "language": item["language"],
                            "date_extraction": item["date_extraction"]
                        }
                    )
                
                # Classer l'élément comme nouveau ou mis à jour
                if status == "new":
                    self.new_faq_items.append({
                        "url": url,
                        "question": item["question"],
                        "data_file": file_path
                    })
                    logger.info(f"Nouvel élément de FAQ: {item['question']}")
                else:
                    self.updated_faq_items.append({
                        "url": url,
                        "question": item["question"],
                        "data_file": file_path,
                        "version": previous.get("version", 0) + 1 if previous else 1
                    })
                    logger.info(f"Élément de FAQ mis à jour: {item['question']}")
            else:
                # Élément inchangé
                self.unchanged_faq_items.append({
                    "url": url,
                    "question": item["question"],
                    "data_file": previous.get("data_file") if previous else None,
                    "version": previous.get("version", 1) if previous else 1
                })
                logger.info(f"Élément de FAQ inchangé: {item['question']}")
        
        # Générer les statistiques
        stats = {
            "new_count": len(self.new_faq_items),
            "updated_count": len(self.updated_faq_items),
            "unchanged_count": len(self.unchanged_faq_items),
            "total_count": len(faq_items)
        }
        
        return stats
    
    def save_report(self) -> str:
        """
        Sauvegarde un rapport de l'exécution
        
        Returns:
            Chemin du fichier de rapport
        """
        # Créer le répertoire des rapports s'il n'existe pas
        os.makedirs(REPORTS_DIR, exist_ok=True)
        
        # Générer le rapport
        report = {
            "timestamp": datetime.now().isoformat(),
            "new_items": self.new_faq_items,
            "updated_items": self.updated_faq_items,
            "unchanged_count": len(self.unchanged_faq_items),
            "total_count": len(self.new_faq_items) + len(self.updated_faq_items) + len(self.unchanged_faq_items),
            "statistics": {
                "new_count": len(self.new_faq_items),
                "updated_count": len(self.updated_faq_items),
                "unchanged_count": len(self.unchanged_faq_items)
            }
        }
        
        # Sauvegarder le rapport
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = os.path.join(REPORTS_DIR, f"faq_report_{timestamp}.json")
        
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Rapport sauvegardé: {report_file}")
        
        return report_file
    
    async def run(self) -> Dict[str, Any]:
        """
        Exécute le scraping de la FAQ
        
        Returns:
            Résultats du scraping
        """
        logger.info(f"Démarrage du scraping de la FAQ: {FAQ_URLS[0]}")
        
        try:
            # Initialiser le scraper
            if not await self.initialize():
                return {"error": "Échec de l'initialisation"}
            
            # Visiter la page de FAQ
            await self.page.goto(FAQ_URLS[0], wait_until="networkidle")
            logger.info("Page de FAQ chargée")
            
            # Attendre que le contenu soit chargé
            await asyncio.sleep(2)
            
            # Extraire les éléments de FAQ
            faq_items = await self.extract_faq_items(self.page)
            
            if not faq_items:
                logger.warning("Aucun élément de FAQ trouvé")
                await self.close()
                return {"error": "Aucun élément de FAQ trouvé"}
            
            # Traiter les éléments de FAQ
            stats = await self.process_faq_items(faq_items)
            
            # Sauvegarder le rapport
            report_file = self.save_report()
            
            # Fermer le navigateur
            await self.close()
            
            # Résultats
            results = {
                "status": "success",
                "new_items": self.new_faq_items,
                "updated_items": self.updated_faq_items,
                "stats": stats,
                "report_file": report_file
            }
            
            return results
            
        except Exception as e:
            logger.error(f"Erreur lors du scraping de la FAQ: {e}")
            
            # Fermer le navigateur en cas d'erreur
            await self.close()
            
            return {"error": str(e)}

async def main():
    """
    Fonction principale
    """
    scraper = FAQScraper()
    results = await scraper.run()
    print(json.dumps(results, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(main())
