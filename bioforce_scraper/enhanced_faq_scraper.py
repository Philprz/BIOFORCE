"""
Module spécialisé pour le scraping et le filtrage intelligent de la FAQ Bioforce
"""
import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

from playwright.async_api import async_playwright, Page

from bioforce_scraper.config import (BASE_URL, DATA_DIR, FAQ_URL, LOG_FILE, REPORTS_DIR, 
                   REQUEST_DELAY, USER_AGENT, OPENAI_API_KEY, COMPLETION_MODEL, EMBEDDING_MODEL)
from bioforce_scraper.utils.content_tracker import ContentTracker
from bioforce_scraper.utils.language_detector import detect_language
from bioforce_scraper.utils.logger import setup_logger
from bioforce_scraper.utils.embeddings import generate_embeddings
from bioforce_scraper.utils.qdrant_connector import QdrantConnector
from openai import AsyncOpenAI

# Configuration du logger
logger = setup_logger(__name__, LOG_FILE)

class EnhancedFAQScraper:
    """
    Scraper spécialisé pour la FAQ Bioforce avec filtrage intelligent par GPT
    """
    
    def __init__(self, force_update=False):
        """
        Initialise le scraper de FAQ amélioré
        
        Args:
            force_update: Force la mise à jour même pour le contenu inchangé
        """
        self.visited_urls = set()
        self.force_update = force_update
        self.content_tracker = ContentTracker()
        self.new_faq_items = []
        self.updated_faq_items = []
        self.unchanged_faq_items = []
        self.filtered_out_items = []
        self.browser = None
        self.context = None
        self.page = None
        self.qdrant = QdrantConnector(is_full_site=False)  # Collection FAQ
        self.openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        self.faq_urls = [
            "https://www.bioforce.org/faq/",
            "https://www.bioforce.org/en/faq/"
        ]
    
    async def initialize(self):
        """
        Initialise le navigateur et la page Playwright
        """
        logger.info("Initialisation du scraper de FAQ amélioré")
        try:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch()
            self.context = await self.browser.new_context(
                user_agent=USER_AGENT
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
    
    async def extract_faq_items_hybrid(self, page: Page) -> List[Dict[str, Any]]:
        """
        Extrait tous les éléments de FAQ depuis la page en utilisant une approche hybride
        
        Args:
            page: Page Playwright
            
        Returns:
            Liste des éléments de FAQ extraits
        """
        logger.info("Extraction des éléments de FAQ avec l'approche hybride")
        
        try:
            # Attendre que la page soit chargée
            await page.wait_for_load_state("networkidle", timeout=30000)
            
            # Extraction des catégories avec approche hybride
            categories = await page.evaluate("""
                () => {
                    const categories = [];
                    
                    // 1. STRATÉGIE PRINCIPALE - RECHERCHE DE H4/DIV
                    document.querySelectorAll('h4.title, h4.faq-title, h4').forEach((titleEl, index) => {
                        const title = titleEl.textContent.trim();
                        const items = [];
                        
                        // Chercher des div.desc qui suivent ce h4
                        let nextEl = titleEl.nextElementSibling;
                        while (nextEl && nextEl.tagName !== 'H4') {
                            if (nextEl.matches('div.desc, div.description')) {
                                const question = nextEl.getAttribute('data-question') || 
                                                nextEl.querySelector('h5, strong')?.textContent.trim() || 
                                                `Question ${items.length + 1}`;
                                                
                                const answerEl = nextEl.querySelector('p') || nextEl;
                                
                                items.push({
                                    question: question,
                                    answer: answerEl.textContent.trim(),
                                    answer_html: answerEl.innerHTML
                                });
                            }
                            nextEl = nextEl.nextElementSibling;
                        }
                        
                        // Si rien trouvé, essayer de détecter des structures FAQ dans le DOM
                        if (items.length === 0) {
                            // Rechercher les questions par texte
                            const faqContainer = titleEl.closest('section, article, div.faq, div.faqs');
                            if (faqContainer) {
                                faqContainer.querySelectorAll('h5, h6, p, div').forEach(el => {
                                    const text = el.textContent.trim();
                                    
                                    // Détecter si c'est une question
                                    if (text.endsWith('?') || 
                                        text.toLowerCase().includes('comment') || 
                                        text.toLowerCase().includes('quand') || 
                                        text.toLowerCase().includes('pourquoi') || 
                                        text.toLowerCase().includes('puis-je') ||
                                        text.toLowerCase().includes('how') || 
                                        text.toLowerCase().includes('what') || 
                                        text.toLowerCase().includes('when')) {
                                        
                                        // Chercher une réponse dans l'élément suivant
                                        const nextElement = el.nextElementSibling;
                                        if (nextElement && nextElement.textContent.trim().length > 10) {
                                            items.push({
                                                question: text,
                                                answer: nextElement.textContent.trim(),
                                                answer_html: nextElement.innerHTML
                                            });
                                        }
                                    }
                                });
                            }
                        }
                        
                        // Si des éléments ont été trouvés, ajouter la catégorie
                        if (items.length > 0) {
                            categories.push({
                                title: title,
                                items: items
                            });
                        }
                    });
                    
                    // 2. STRATÉGIE ALTERNATIVE - RECHERCHE D'ACCORDÉON
                    // Si aucune catégorie n'a été trouvée avec la méthode précédente
                    if (categories.length === 0) {
                        document.querySelectorAll('.accordion').forEach((accordion, index) => {
                            // Trouver le titre de la catégorie (élément précédent)
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
                    }
                    
                    return categories;
                }
            """)
            
            # Aplatir les catégories en une liste d'éléments FAQ
            faq_items = []
            for category in categories:
                category_title = category["title"]
                for item in category["items"]:
                    # Éviter les questions vides ou trop courtes
                    if len(item["question"].strip()) < 5 or len(item["answer"].strip()) < 10:
                        continue
                        
                    faq_items.append({
                        "category": category_title,
                        "question": item["question"],
                        "answer": item["answer"],
                        "answer_html": item["answer_html"],
                        "url": page.url + "#" + self._generate_anchor(item["question"]),
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
    
    async def filter_with_gpt(self, faq_items: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Filtre les éléments FAQ avec GPT pour ne garder que les informations utiles
        
        Args:
            faq_items: Liste des éléments FAQ à filtrer
            
        Returns:
            Tuple contenant (éléments conservés, éléments filtrés)
        """
        logger.info(f"Filtrage intelligent de {len(faq_items)} éléments avec {COMPLETION_MODEL}")
        
        kept_items = []
        filtered_items = []
        
        for item in faq_items:
            try:
                # Construire le prompt en fonction de la langue
                is_french = item["language"] == "fr"
                
                system_prompt = """
                Tu es un assistant spécialisé dans le filtrage de contenu pour un chatbot de l'organisation Bioforce.
                Tu dois évaluer si l'élément de FAQ fourni est utile pour répondre aux questions des candidats 
                concernant les formations, le processus de sélection et les modalités d'inscription.
                
                CRITÈRES DE SÉLECTION:
                1. Pertinence pour les candidats à une formation Bioforce
                2. Actualité et précision de l'information
                3. Format adapté aux requêtes d'un chatbot
                
                Ton rôle est d'évaluer l'élément et de le reformuler/améliorer si nécessaire.
                """
                
                if is_french:
                    user_prompt = f"""
                    Voici un élément de FAQ extrait du site Bioforce:
                    
                    Catégorie: {item['category']}
                    Question: {item['question']}
                    Réponse: {item['answer']}
                    
                    1. Cet élément est-il utile pour le chatbot? (Réponds par OUI ou NON)
                    2. Si OUI, propose une version améliorée de la réponse qui conserve toutes les informations importantes 
                       mais qui est optimisée pour un chatbot (plus concise, structurée, informative).
                    3. Si NON, explique brièvement pourquoi.
                    
                    Commence ta réponse par "DÉCISION: OUI" ou "DÉCISION: NON".
                    """
                else:
                    user_prompt = f"""
                    Here is a FAQ item extracted from the Bioforce website:
                    
                    Category: {item['category']}
                    Question: {item['question']}
                    Answer: {item['answer']}
                    
                    1. Is this item useful for the chatbot? (Answer with YES or NO)
                    2. If YES, provide an improved version of the answer that keeps all important information
                       but is optimized for a chatbot (more concise, structured, informative).
                    3. If NO, briefly explain why.
                    
                    Start your response with "DECISION: YES" or "DECISION: NO".
                    """
                
                # Appel à GPT
                response = await self.openai_client.chat.completions.create(
                    model=COMPLETION_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.3,
                    max_tokens=500
                )
                
                gpt_response = response.choices[0].message.content
                
                # Analyser la décision
                if gpt_response.startswith("DÉCISION: OUI") or gpt_response.startswith("DECISION: YES"):
                    # Extraire la réponse améliorée
                    improved_answer = ""
                    
                    if is_french:
                        # Trouver le texte après "propose une version améliorée"
                        if "version améliorée" in gpt_response:
                            improved_parts = gpt_response.split("version améliorée")
                            if len(improved_parts) > 1:
                                improved_answer = improved_parts[1].strip()
                    else:
                        # Trouver le texte après "improved version"
                        if "improved version" in gpt_response.lower():
                            improved_parts = gpt_response.lower().split("improved version")
                            if len(improved_parts) > 1:
                                improved_answer = improved_parts[1].strip()
                    
                    # Si pas d'amélioration claire, prendre tout après la décision
                    if not improved_answer:
                        decision_text = "DÉCISION: OUI" if is_french else "DECISION: YES"
                        improved_parts = gpt_response.split(decision_text)
                        if len(improved_parts) > 1:
                            improved_answer = improved_parts[1].strip()
                    
                    # Si toujours pas d'amélioration, garder la réponse originale
                    if not improved_answer:
                        improved_answer = item["answer"]
                    
                    # Créer une copie de l'élément avec la réponse améliorée
                    improved_item = item.copy()
                    improved_item["answer"] = improved_answer
                    improved_item["gpt_enhanced"] = True
                    
                    kept_items.append(improved_item)
                    logger.info(f"Élément conservé et amélioré: {item['question'][:50]}...")
                else:
                    # Élément filtré
                    filtered_items.append(item)
                    logger.info(f"Élément filtré: {item['question'][:50]}...")
                
                # Attendre un peu pour ne pas surcharger l'API
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Erreur lors du filtrage par GPT: {e}")
                # En cas d'erreur, conserver l'élément original par précaution
                kept_items.append(item)
        
        logger.info(f"Filtrage terminé: {len(kept_items)} éléments conservés, {len(filtered_items)} éléments filtrés")
        return kept_items, filtered_items
    
    async def process_faq_items(self, faq_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Traite les éléments de FAQ extraits (vérifie les nouveautés, mises à jour)
        
        Args:
            faq_items: Liste des éléments de FAQ extraits
            
        Returns:
            Statistiques de traitement
        """
        logger.info(f"Traitement de {len(faq_items)} éléments de FAQ")
        
        # Filtrer avec GPT
        filtered_items, filtered_out = await self.filter_with_gpt(faq_items)
        self.filtered_out_items.extend(filtered_out)
        
        # Utiliser ContentTracker pour gérer les nouveautés et mises à jour
        stats = {
            "total": len(faq_items),
            "kept": len(filtered_items),
            "filtered_out": len(filtered_out),
            "new": 0,
            "updated": 0,
            "unchanged": 0
        }
        
        for item in filtered_items:
            item_key = f"{item['url']}_{item['language']}"
            content_hash = self.content_tracker.calculate_hash(item)
            
            if self.content_tracker.is_new_content(item_key, content_hash) or self.force_update:
                if self.content_tracker.content_exists(item_key):
                    # Contenu mis à jour
                    self.updated_faq_items.append(item)
                    stats["updated"] += 1
                else:
                    # Nouveau contenu
                    self.new_faq_items.append(item)
                    stats["new"] += 1
                    
                # Mettre à jour le tracker
                self.content_tracker.update_content(item_key, content_hash)
            else:
                # Contenu inchangé
                self.unchanged_faq_items.append(item)
                stats["unchanged"] += 1
        
        logger.info(f"Traitement terminé: {stats['new']} nouveaux, {stats['updated']} mis à jour, {stats['unchanged']} inchangés")
        return stats
    
    async def index_faq_items(self) -> None:
        """
        Indexe les éléments de FAQ dans Qdrant
        """
        all_items = self.new_faq_items + self.updated_faq_items
        
        if not all_items:
            logger.info("Aucun nouvel élément ou mise à jour à indexer")
            return
            
        logger.info(f"Indexation de {len(all_items)} éléments dans Qdrant")
        
        for item in all_items:
            try:
                # Générer l'embedding pour le texte combiné
                combined_text = f"{item['category']} - {item['question']}: {item['answer']}"
                embedding = await generate_embeddings(combined_text)
                
                if not embedding:
                    logger.error(f"Impossible de générer l'embedding pour: {item['question']}")
                    continue
                
                # Préparer les métadonnées
                metadata = {
                    "category": item["category"],
                    "question": item["question"],
                    "answer": item["answer"],
                    "url": item["url"],
                    "language": item["language"],
                    "date_extraction": item["date_extraction"],
                    "content_type": "faq"
                }
                
                # Indexer dans Qdrant
                point_id = self.qdrant.generate_point_id(item["url"], item["language"])
                await self.qdrant.add_point(point_id, embedding, metadata)
                logger.info(f"Élément indexé: {item['question'][:50]}...")
                
            except Exception as e:
                logger.error(f"Erreur lors de l'indexation: {e}")
    
    async def save_reports(self) -> None:
        """
        Sauvegarde les rapports de scraping
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Créer le répertoire de rapports s'il n'existe pas
        os.makedirs(REPORTS_DIR, exist_ok=True)
        
        # Rapport des nouveaux éléments
        if self.new_faq_items:
            new_items_file = os.path.join(REPORTS_DIR, f"new_faq_items_{timestamp}.json")
            with open(new_items_file, "w", encoding="utf-8") as f:
                json.dump(self.new_faq_items, f, ensure_ascii=False, indent=2)
            logger.info(f"Rapport des nouveaux éléments sauvegardé: {new_items_file}")
        
        # Rapport des éléments mis à jour
        if self.updated_faq_items:
            updated_items_file = os.path.join(REPORTS_DIR, f"updated_faq_items_{timestamp}.json")
            with open(updated_items_file, "w", encoding="utf-8") as f:
                json.dump(self.updated_faq_items, f, ensure_ascii=False, indent=2)
            logger.info(f"Rapport des éléments mis à jour sauvegardé: {updated_items_file}")
        
        # Rapport des éléments filtrés
        if self.filtered_out_items:
            filtered_items_file = os.path.join(REPORTS_DIR, f"filtered_faq_items_{timestamp}.json")
            with open(filtered_items_file, "w", encoding="utf-8") as f:
                json.dump(self.filtered_out_items, f, ensure_ascii=False, indent=2)
            logger.info(f"Rapport des éléments filtrés sauvegardé: {filtered_items_file}")
    
    async def run(self) -> Dict[str, Any]:
        """
        Exécute le scraping de la FAQ
        
        Returns:
            Statistiques de scraping
        """
        if not await self.initialize():
            return {"status": "error", "message": "Échec de l'initialisation"}
        
        try:
            stats = {
                "total_extracted": 0,
                "total_kept": 0,
                "total_filtered_out": 0,
                "total_new": 0,
                "total_updated": 0,
                "total_unchanged": 0,
                "urls_processed": 0,
                "urls_failed": 0,
                "urls_details": []
            }
            
            # Scraper chaque URL de FAQ
            for url in self.faq_urls:
                logger.info(f"Démarrage du scraping de la FAQ: {url}")
                
                try:
                    # Naviguer vers l'URL
                    await self.page.goto(url, wait_until="networkidle")
                    await asyncio.sleep(REQUEST_DELAY)
                    
                    # Extraire les éléments
                    faq_items = await self.extract_faq_items_hybrid(self.page)
                    
                    if faq_items:
                        # Traiter les éléments extraits
                        url_stats = await self.process_faq_items(faq_items)
                        
                        # Mettre à jour les statistiques globales
                        stats["total_extracted"] += url_stats["total"]
                        stats["total_kept"] += url_stats["kept"]
                        stats["total_filtered_out"] += url_stats["filtered_out"]
                        stats["total_new"] += url_stats["new"]
                        stats["total_updated"] += url_stats["updated"]
                        stats["total_unchanged"] += url_stats["unchanged"]
                        stats["urls_processed"] += 1
                        
                        # Détails pour cette URL
                        stats["urls_details"].append({
                            "url": url,
                            "status": "success",
                            "extracted": url_stats["total"],
                            "kept": url_stats["kept"],
                            "filtered_out": url_stats["filtered_out"]
                        })
                        
                        logger.info(f"Scraping réussi pour {url}: {len(faq_items)} éléments extraits")
                    else:
                        stats["urls_failed"] += 1
                        stats["urls_details"].append({
                            "url": url,
                            "status": "no_items_found"
                        })
                        logger.warning(f"Aucun élément trouvé pour {url}")
                        
                except Exception as e:
                    stats["urls_failed"] += 1
                    stats["urls_details"].append({
                        "url": url,
                        "status": "error",
                        "message": str(e)
                    })
                    logger.error(f"Erreur lors du scraping de {url}: {e}")
            
            # Indexer les éléments dans Qdrant
            await self.index_faq_items()
            
            # Sauvegarder les rapports
            await self.save_reports()
            
            stats["status"] = "success"
            return stats
            
        except Exception as e:
            logger.error(f"Erreur lors du scraping de la FAQ: {e}")
            return {"status": "error", "message": str(e)}
        finally:
            await self.close()

async def main():
    """
    Fonction principale
    """
    logger.info("Démarrage du scraping amélioré de la FAQ Bioforce")
    
    # Créer et exécuter le scraper
    scraper = EnhancedFAQScraper()
    stats = await scraper.run()
    
    # Afficher les statistiques
    if stats["status"] == "success":
        logger.info(f"Scraping terminé avec succès: {stats['total_kept']} éléments conservés sur {stats['total_extracted']} extraits")
        logger.info(f"Nouveaux: {stats['total_new']}, Mis à jour: {stats['total_updated']}, Inchangés: {stats['total_unchanged']}, Filtrés: {stats['total_filtered_out']}")
    else:
        logger.error(f"Échec du scraping: {stats.get('message', 'Erreur inconnue')}")

if __name__ == "__main__":
    asyncio.run(main())
