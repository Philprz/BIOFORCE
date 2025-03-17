"""
Module principal pour le scraper Bioforce
"""
import asyncio
import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Set
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page, Browser

from bioforce_scraper.config import (BASE_URL, DATA_DIR, EXCLUDE_PATTERNS, LOG_FILE,
                   MAX_PAGES, PDF_DIR, PRIORITY_PATTERNS, 
                   REQUEST_DELAY, START_URLS, USER_AGENT)
from bioforce_scraper.utils.content_tracker import ContentTracker
from bioforce_scraper.utils.embeddings import generate_embeddings
from bioforce_scraper.utils.language_detector import detect_language
from bioforce_scraper.utils.logger import setup_logger
from bioforce_scraper.utils.qdrant_connector import QdrantConnector
from bioforce_scraper.utils.robots_parser import RobotsParser
from bioforce_scraper.utils.url_prioritizer import prioritize_url

# Configuration du logger
logger = setup_logger(__name__, LOG_FILE)

class BioforceScraperMain:
    def __init__(self, incremental=True):
        self.visited_urls = set()
        self.queue = []
        self.extracted_data = []
        self.updated_data = []
        self.unchanged_data = []
        self.pdf_count = 0
        self.html_count = 0
        self.skipped_count = 0
        self.new_content_count = 0
        self.updated_content_count = 0
        self.unchanged_content_count = 0
        self.robots_parser = None
        self.browser = None
        self.context = None
        self.content_tracker = ContentTracker() if incremental else None
        self.incremental = incremental
        self.qdrant = QdrantConnector(is_full_site=True)  # Utilise la collection pour le site complet

    async def initialize(self):
        """Initialise le scraper en démarrant Playwright et en chargeant robots.txt"""
        logger.info("Initialisation du scraper Bioforce")
        
        # Initialisation du parser robots.txt
        self.robots_parser = RobotsParser(BASE_URL)
        await self.robots_parser.load()
        
        # Initialisation de Playwright
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 800}
        )
        
        # En mode incrémental, charger les URLs déjà connues
        if self.incremental and self.content_tracker:
            known_urls = set(self.content_tracker.get_all_tracked_urls())
            logger.info(f"Chargement de {len(known_urls)} URLs déjà connues")
        else:
            known_urls = set()
        
        # Ajout des URLs de départ à la file d'attente
        for url in START_URLS:
            # En mode incrémental, on vérifie quand même les URLs de départ
            # même si elles sont déjà connues (pour détecter les mises à jour)
            self.queue.append({"url": url, "priority": 10, "depth": 0})
        
        logger.info(f"File d'attente initialisée avec {len(self.queue)} URLs de départ")
        logger.info(f"Mode incrémental: {self.incremental}")

    async def close(self):
        """Ferme les ressources"""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            # Ajouter un petit délai pour permettre la libération des ressources
            await asyncio.sleep(0.5)
            logger.info("Ressources libérées")
        except Exception as e:
            logger.error(f"Erreur lors de la fermeture des ressources: {str(e)}")

    async def run(self):
        """Exécute le processus de scraping"""
        await self.initialize()
        
        try:
            progress_bar = tqdm(total=MAX_PAGES, desc="Pages scrapées")
            
            while self.queue and len(self.visited_urls) < MAX_PAGES:
                # Trie la file d'attente par priorité (la plus élevée d'abord)
                self.queue.sort(key=lambda x: x["priority"], reverse=True)
                
                # Extraire l'URL avec la priorité la plus élevée
                current = self.queue.pop(0)
                url = current["url"]
                depth = current["depth"]
                
                # Vérifier si l'URL a déjà été visitée dans cette session
                if url in self.visited_urls:
                    continue
                
                # Vérifier si l'URL est autorisée par robots.txt
                if not self.robots_parser.can_fetch(url):
                    logger.info(f"URL non autorisée par robots.txt: {url}")
                    continue
                
                self.visited_urls.add(url)
                
                # En mode incrémental, vérifier si le contenu est déjà connu
                # Mais continuer quand même pour vérifier les mises à jour
                is_known = False
                if self.incremental and self.content_tracker:
                    known_urls = self.content_tracker.get_all_tracked_urls()
                    is_known = url in known_urls
                
                # Respecter le délai entre les requêtes
                await asyncio.sleep(REQUEST_DELAY)
                
                try:
                    # Traiter l'URL en fonction de son type
                    if url.lower().endswith('.pdf'):
                        data = await self.process_pdf(url)
                        if data:
                            self.pdf_count += 1
                            status = self.update_content_status(url, data)
                    else:
                        data, new_urls = await self.process_html(url, depth)
                        if data:
                            self.html_count += 1
                            status = self.update_content_status(url, data)
                            
                            # Ajouter les nouvelles URLs à la file d'attente
                            for new_url in new_urls:
                                if new_url not in self.visited_urls and self.is_valid_url(new_url):
                                    # Vérifier si c'est un PDF (pour augmenter sa priorité)
                                    is_pdf = new_url.lower().endswith('.pdf')
                                    priority = prioritize_url(new_url, PRIORITY_PATTERNS)
                                    
                                    # Augmenter la priorité des PDFs
                                    if is_pdf:
                                        priority += 5
                                        
                                    self.queue.append({
                                        "url": new_url, 
                                        "priority": priority, 
                                        "depth": depth + 1
                                    })
                    
                    # Si aucune donnée n'a été extraite
                    if not data:
                        self.skipped_count += 1
                        
                except Exception as e:
                    logger.error(f"Erreur lors du traitement de {url}: {str(e)}")
                    self.skipped_count += 1
                
                progress_bar.update(1)
                progress_bar.set_postfix({
                    'HTML': self.html_count, 
                    'PDF': self.pdf_count, 
                    'Queue': len(self.queue),
                    'Nouveaux': self.new_content_count,
                    'Mis à jour': self.updated_content_count
                })
            
            progress_bar.close()
            
            # Sauvegarder les données extraites
            self.save_data()
            
            # Afficher des statistiques sur les contenus traités
            if self.incremental and self.content_tracker:
                stats = self.content_tracker.get_content_stats()
                logger.info(f"Statistiques totales de la base de contenu: {json.dumps(stats, indent=2)}")
            
            logger.info(f"Scraping terminé: {self.html_count} pages HTML, {self.pdf_count} PDF, {self.skipped_count} ignorés")
            logger.info(f"Nouveaux contenus: {self.new_content_count}, Mises à jour: {self.updated_content_count}, Inchangés: {self.unchanged_content_count}")
            logger.info(f"Total URLs visitées: {len(self.visited_urls)}")
            
            # Indexer les données dans Qdrant
            await self.index_data_in_qdrant()
            
        finally:
            await self.close()

    async def index_data_in_qdrant(self):
        """Indexe les données extraites dans Qdrant"""
        logger.info("Indexation des données dans Qdrant (collection site complet)")
        
        # Nombre de documents à traiter
        total_docs = len(self.extracted_data) + len(self.updated_data)
        indexed_count = 0
        error_count = 0
        
        # Indexer le nouveau contenu et le contenu mis à jour
        for document in self.extracted_data + self.updated_data:
            try:
                # Skip si le document n'a pas de contenu
                if not document.get("content") or not document.get("title"):
                    continue
                
                # Générer un ID unique pour le document basé sur l'URL
                doc_id = hashlib.md5(document["url"].encode()).hexdigest()
                
                # Générer les embeddings pour le document
                content_to_embed = f"TITLE: {document['title']}\n\nCONTENT: {document['content']}"
                
                # Générer l'embedding
                embedding = await generate_embeddings(content_to_embed)
                
                if embedding:
                    # Métadonnées pour le document
                    payload = {
                        "title": document["title"],
                        "content": document["content"],
                        "source_url": document["url"],
                        "type": document.get("type", "page"),
                        "category": document.get("category", "général"),
                        "language": document.get("language", "fr"),
                        "extraction_date": datetime.now().isoformat(),
                    }
                    
                    # Ajouter le document à Qdrant
                    result = self.qdrant.upsert_document(doc_id, embedding, payload)
                    
                    if result:
                        indexed_count += 1
                        logger.info(f"Document indexé avec succès: {document['url']}")
                    else:
                        error_count += 1
                        logger.error(f"Échec de l'indexation pour: {document['url']}")
                else:
                    error_count += 1
                    logger.error(f"Échec de génération d'embedding pour: {document['url']}")
            
            except Exception as e:
                error_count += 1
                logger.error(f"Erreur lors de l'indexation du document {document.get('url')}: {e}")
        
        logger.info(f"Indexation terminée: {indexed_count}/{total_docs} documents indexés, {error_count} erreurs")

    def update_content_status(self, url, data):
        """
        Met à jour le statut du contenu et le tracker
        
        Args:
            url: URL du contenu
            data: Données extraites
            
        Returns:
            Statut du contenu ('new', 'updated', 'unchanged')
        """
        if not self.incremental or not self.content_tracker:
            self.extracted_data.append(data)
            self.new_content_count += 1
            return 'new'
        
        # Vérifier le statut du contenu
        status, is_changed, previous = self.content_tracker.check_content_status(url, data)
        
        # Mettre à jour les compteurs et listes de données
        if status == 'new':
            self.new_content_count += 1
            self.extracted_data.append(data)
        elif status == 'updated':
            self.updated_content_count += 1
            # Ajouter des métadonnées sur la mise à jour
            data['previous_version'] = previous.get('version', 0)
            data['update_timestamp'] = datetime.now().isoformat()
            self.updated_data.append(data)
            self.extracted_data.append(data)
        else:  # unchanged
            self.unchanged_content_count += 1
            self.unchanged_data.append(data)
        
        # Mettre à jour la base de données de suivi
        self.content_tracker.update_content_record(url, data, status)
        
        return status

    def is_valid_url(self, url):
        """Vérifie si une URL est valide pour le scraping"""
        # Vérifier si l'URL appartient au domaine bioforce.org
        parsed_url = urlparse(url)
        if parsed_url.netloc and "bioforce.org" not in parsed_url.netloc:
            return False
        
        # Vérifier les patterns d'exclusion
        for pattern in EXCLUDE_PATTERNS:
            if pattern in url:
                return False
        
        return True

    async def process_html(self, url, depth):
        """Traite une page HTML"""
        logger.info(f"Traitement de la page HTML: {url}")
        
        page = await self.context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            # Extraire le contenu de la page
            content = await extract_page_content(page)
            
            # Extraire les liens de la page
            links = await page.evaluate("""() => {
                const anchors = Array.from(document.querySelectorAll('a'));
                return anchors.map(a => a.href);
            }""")
            
            # Rechercher spécifiquement les liens PDF
            pdf_links = await page.evaluate("""() => {
                const anchors = Array.from(document.querySelectorAll('a[href$=".pdf"]'));
                return anchors.map(a => a.href);
            }""")
            
            # Ajouter les liens PDF en tête de liste avec une priorité élevée
            pdf_urls = []
            for pdf_link in pdf_links:
                if pdf_link and pdf_link.lower().endswith('.pdf'):
                    full_url = urljoin(url, pdf_link)
                    pdf_urls.append(full_url)
            
            # Filtrer et normaliser les liens normaux
            regular_urls = []
            for link in links:
                if link and not link.startswith('javascript:') and not link.startswith('#'):
                    # Convertir en URL absolue
                    full_url = urljoin(url, link)
                    if full_url not in pdf_urls:  # Éviter les doublons
                        regular_urls.append(full_url)
            
            # Combiner les deux listes, avec les PDFs en premier
            new_urls = pdf_urls + regular_urls
            
            # Vérifier si le contenu a été extrait avec succès
            if not content or not content.get('content'):
                logger.warning(f"Aucun contenu extrait de {url}")
                return None, new_urls
            
            # Détecter la langue
            language = detect_language(content.get('content', ''))
            
            # Classifier le contenu
            category = classify_content(url, content.get('title', ''), content.get('content', ''))
            
            # Structurer les données
            data = {
                'source_url': url,
                'title': content.get('title', ''),
                'content': content.get('content', ''),
                'headings': content.get('headings', []),
                'metadata': content.get('metadata', {}),
                'type': 'html',
                'language': language,
                'category': category,
                'date_extraction': datetime.now().isoformat()
            }
            
            return data, new_urls
            
        except Exception as e:
            logger.error(f"Erreur lors du traitement de la page HTML {url}: {str(e)}")
            return None, []
            
        finally:
            await page.close()

    async def process_pdf(self, url):
        """Traite un fichier PDF"""
        logger.info(f"Traitement du PDF: {url}")
        
        try:
            # Extraire le contenu du PDF
            pdf_data = await extract_pdf_content(url)
            
            if not pdf_data or not pdf_data.get('content'):
                logger.warning(f"Aucun contenu extrait du PDF {url}")
                return None
            
            # Détecter la langue
            language = detect_language(pdf_data.get('content', ''))
            
            # Classifier le contenu
            category = classify_content(url, pdf_data.get('title', ''), pdf_data.get('content', ''))
            
            # Structurer les données
            data = {
                'source_url': url,
                'title': pdf_data.get('title', ''),
                'content': pdf_data.get('content', ''),
                'metadata': pdf_data.get('metadata', {}),
                'type': 'pdf',
                'language': language,
                'category': category,
                'date_extraction': datetime.now().isoformat()
            }
            
            return data
            
        except Exception as e:
            logger.error(f"Erreur lors du traitement du PDF {url}: {str(e)}")
            return None

    def save_data(self):
        """Sauvegarde les données extraites"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Sauvegarder les nouvelles données et mises à jour
        if self.extracted_data:
            filename = os.path.join(DATA_DIR, f"bioforce_data_{timestamp}.json")
            
            # Organisation des données par catégorie
            categorized_data = {category: [] for category in CONTENT_CATEGORIES}
            categorized_data['other'] = []
            
            for item in self.extracted_data:
                category = item.get('category', 'other')
                if category in CONTENT_CATEGORIES:
                    categorized_data[category].append(item)
                else:
                    categorized_data['other'].append(item)
            
            # Statistiques
            stats = {
                'total_items': len(self.extracted_data),
                'new_items': self.new_content_count,
                'updated_items': self.updated_content_count,
                'unchanged_items': self.unchanged_content_count,
                'html_pages': self.html_count,
                'pdfs': self.pdf_count,
                'skipped': self.skipped_count,
                'by_category': {category: len(items) for category, items in categorized_data.items()},
                'date_extraction': datetime.now().isoformat()
            }
            
            # Sauvegarder les données et les statistiques
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump({
                    'stats': stats,
                    'data': self.extracted_data
                }, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Données sauvegardées dans {filename}")
        
        # Sauvegarder les URLs visitées
        urls_file = os.path.join(DATA_DIR, f"bioforce_urls_{timestamp}.txt")
        with open(urls_file, 'w', encoding='utf-8') as f:
            for url in sorted(self.visited_urls):
                f.write(f"{url}\n")
        
        logger.info(f"URLs visitées sauvegardées dans {urls_file}")
        
        # Générer un rapport des changements si en mode incrémental
        if self.incremental and self.content_tracker and (self.new_content_count > 0 or self.updated_content_count > 0):
            report = self.content_tracker.generate_change_report()
            report_file = os.path.join(DATA_DIR, f"bioforce_changes_{timestamp}.json")
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            logger.info(f"Rapport des changements sauvegardé dans {report_file}")

async def main():
    """Fonction principale"""
    start_time = time.time()
    logger.info("Démarrage du scraper Bioforce")
    
    # Par défaut, utiliser le mode incrémental
    incremental = True
    scraper = BioforceScraperMain(incremental=incremental)
    await scraper.run()
    
    elapsed_time = time.time() - start_time
    logger.info(f"Scraping terminé en {elapsed_time:.2f} secondes")

if __name__ == "__main__":
    asyncio.run(main())
