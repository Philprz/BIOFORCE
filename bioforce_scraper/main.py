"""
Module principal pour le scraper Bioforce
"""
import asyncio
from bioforce_scraper.extractors.html_extractor import extract_page_content # Importation de la fonction extract_page_content
from tqdm import tqdm # Import de tqdm pour éviter le NameError
from bioforce_scraper.utils.classifier import classify_content  
import hashlib
import json
import logging
import os
import re
import time
import traceback
import uuid
import aiohttp
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
from bioforce_scraper.utils.sitemap_parser import SitemapParser
from bioforce_scraper.utils.content_classifier import ContentClassifier

# Configuration du logger
logger = setup_logger(__name__, LOG_FILE)

# Catégories de contenu pour la classification
CONTENT_CATEGORIES = ["page", "pdf", "faq", "général", "formation", "article", "actualité"]

class BioforceScraperMain:
    def __init__(self, incremental=True):
        self.visited_urls = set()
        self.queue = []  # File des URLs à visiter
        self.scraped_data = []  # Données scrapées
        self.failed_urls = []  # URLs en échec
        self.extracted_contents = []  # Contenus extraits
        self.incremental = incremental
        self.robots_parser = None
        self.browser = None
        self.context = None
        self.content_tracker = ContentTracker()
        self.content_classifier = ContentClassifier()  # Initialisation du classifieur de contenu
        self.doc_batch = []  # Batch de documents à indexer dans Qdrant
        self.qdrant_connector = QdrantConnector()
        self.pdf_count = 0
        self.html_count = 0
        self.skipped_count = 0
        self.new_content_count = 0
        self.updated_content_count = 0
        self.unchanged_content_count = 0
        self.batch_count = 0  # Compteur pour l'envoi par lot
        self.batch_size = 20  # Taille du lot pour l'envoi à Qdrant

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
        
        # Utiliser le parser de sitemap pour obtenir les URLs prioritaires
        logger.info("Récupération des URLs depuis le sitemap XML...")
        sitemap_parser = SitemapParser()
        sitemap_urls = await sitemap_parser.run()
        
        if sitemap_urls:
            # Ajouter les URLs du sitemap à la file d'attente
            for url_info in sitemap_urls:
                # Si l'URL est déjà connue mais qu'on est en mode incrémental,
                # on la vérifie quand même pour détecter les mises à jour
                self.queue.append(url_info)
            
            logger.info(f"File d'attente initialisée avec {len(sitemap_urls)} URLs depuis le sitemap")
        else:
            # Fallback sur les URLs de départ prédéfinies si le sitemap n'est pas disponible
            logger.warning("Pas d'URLs trouvées dans le sitemap, utilisation des URLs de départ par défaut")
            for url in START_URLS:
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
        logger.info("Démarrage du scraper Bioforce")
        
        await self.initialize()
        
        try:
            logger.info(f"Début du scraping, limite: {MAX_PAGES} pages")
            
            # Compteur pour le nombre de pages traitées
            processed_count = 0
            batch_count = 0
            
            # Traiter la file d'attente jusqu'à ce qu'elle soit vide ou qu'on atteigne la limite
            while self.queue and len(self.visited_urls) < MAX_PAGES:
                # Trier la file d'attente par priorité
                self.queue.sort(key=lambda x: x.get("priority", 0), reverse=True)
                
                # Extraire l'URL avec la priorité la plus élevée
                url_info = self.queue.pop(0)
                url = url_info.get("url")
                depth = url_info.get("depth", 0)
                
                # Vérifier si l'URL a déjà été visitée
                if url in self.visited_urls:
                    continue
                
                # Vérifier si l'URL est autorisée par robots.txt
                if not self.robots_parser.is_allowed(url):
                    logger.info(f"URL non autorisée par robots.txt: {url}")
                    continue
                
                # Marquer l'URL comme visitée
                self.visited_urls.add(url)
                processed_count += 1
                
                # Traiter l'URL
                logger.info(f"Traitement de l'URL ({processed_count}/{MAX_PAGES}): {url}")
                
                if url.endswith(".pdf"):
                    # Traiter un PDF
                    data = await self.process_pdf(url)
                    if data:
                        self.pdf_count += 1
                        # Sauvegarder le document PDF (incluant le filtrage par pertinence)
                        data_to_index = self.save_data(data)
                        if data_to_index:
                            self.doc_batch.append(data_to_index)
                            batch_count += 1
                else:
                    # Traiter une page HTML
                    data, new_urls = await self.process_html(url, depth)
                    
                    if data:
                        self.html_count += 1
                        # Sauvegarder le document HTML (incluant le filtrage par pertinence)
                        data_to_index = self.save_data(data)
                        if data_to_index:
                            self.doc_batch.append(data_to_index)
                            batch_count += 1
                        
                        # Ajouter les nouvelles URLs à la file d'attente
                        for new_url_info in new_urls:
                            if new_url_info.get("url") not in self.visited_urls:
                                self.queue.append(new_url_info)
                
                # Indexer les documents par lots dans Qdrant (toutes les 20 pages)
                if batch_count >= self.batch_size:
                    logger.info(f"Indexation d'un lot de {batch_count} documents dans Qdrant...")
                    await self.batch_index_to_qdrant()
                    batch_count = 0
                
                # Attendre entre chaque requête
                await asyncio.sleep(REQUEST_DELAY)
            
            # Indexer les documents restants dans Qdrant
            if self.doc_batch:
                logger.info(f"Indexation du lot final de {len(self.doc_batch)} documents dans Qdrant...")
                await self.batch_index_to_qdrant()
            
            logger.info(f"Scraping terminé. Pages traitées: {processed_count}")
            logger.info(f"Statistiques: {self.html_count} pages HTML, {self.pdf_count} PDFs, {self.skipped_count} ignorés")
            
        except Exception as e:
            logger.error(f"Erreur lors du scraping: {e}")
            
        finally:
            # Fermer le navigateur
            await self.close()

    async def batch_index_to_qdrant(self):
        """
        Indexe un lot de documents dans Qdrant
        """
        if not self.doc_batch:
            logger.info("Aucun document à indexer")
            return
        
        indexed_count = 0
        error_count = 0
        
        for document in self.doc_batch:
            try:
                # Générer un ID unique pour le document s'il n'en a pas déjà un
                doc_id = document.get("doc_id", str(uuid.uuid4()))
                
                # Générer les embeddings pour le contenu
                content_to_embed = f"{document['title']} {document['content']}"
                if document.get('pdf_content'):
                    content_to_embed += f" {document['pdf_content']}"
                
                embedding = generate_embeddings(content_to_embed)
                
                # Créer le payload pour Qdrant
                payload = {
                    "url": document["url"],
                    "title": document["title"],
                    "content": document["content"],
                    "category": document["category"],
                    "timestamp": document.get("timestamp", ""),
                    "language": document.get("language", ""),
                    "relevance_score": document.get("relevance_score", 0.5),
                    "pdf_path": document.get("pdf_path", ""),
                    "metadata": {
                        "extraction_date": datetime.now().isoformat()
                    }
                }
                
                # Ajouter le document à Qdrant
                result = self.qdrant_connector.upsert_document(doc_id, embedding, payload)
                
                if result:
                    indexed_count += 1
                else:
                    error_count += 1
                    logger.error(f"Erreur lors de l'indexation dans Qdrant: {document['url']}")
                
            except Exception as e:
                error_count += 1
                logger.error(f"Erreur lors de l'indexation dans Qdrant: {str(e)}")
        
        logger.info(f"Indexation terminée: {indexed_count} documents indexés, {error_count} erreurs")
        
        # Vider le batch après l'indexation
        self.doc_batch = []

    def save_data(self, url_data):
        """Sauvegarde les données extraites"""
        url = url_data.get("url", "")
        content = url_data.get("content", "")
        title = url_data.get("title", "")
        timestamp = url_data.get("timestamp", "")
        links = url_data.get("links", [])
        pdf_links = url_data.get("pdf_links", [])
        other_links = url_data.get("other_links", [])
        pdf_content = url_data.get("pdf_content", "")
        pdf_path = url_data.get("pdf_path", "")
        language = detect_language(content)

        # Vérifier si le contenu est pertinent pour l'indexation
        if not self.content_classifier.should_index_content(url_data):
            logger.info(f"Contenu non pertinent, ignoré pour l'indexation: {url}")
            return None

        # Si nous arrivons ici, le contenu est pertinent
        category = url_data.get("category", "général")
        relevance_score = url_data.get("relevance_score", 0.5)
        logger.info(f"Contenu pertinent ({category}, score: {relevance_score:.2f}): {url}")
        
        # Créer un document structuré pour l'indexation
        document = {
            "url": url,
            "title": title,
            "content": content,
            "category": category,
            "timestamp": timestamp,
            "language": language,
            "relevance_score": relevance_score,
            "pdf_content": pdf_content,
            "pdf_path": pdf_path
        }

        # Générer un ID basé sur l'URL et le timestamp (pour détecter les mises à jour)
        import hashlib
        # Utiliser un hash de l'URL comme identifiant de base, plus stable pour les mises à jour
        doc_id = hashlib.md5(url.encode()).hexdigest()
       
        # Si le contenu a un timestamp, l'ajouter à l'ID pour suivre les mises à jour
        if timestamp:
            doc_id = f"{doc_id}_{timestamp.replace(':', '-').replace(' ', '_')}"

        # Archiver les données extraites
        os.makedirs(DATA_DIR, exist_ok=True)
        file_path = os.path.join(DATA_DIR, f"{doc_id}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(document, f, ensure_ascii=False, indent=2)
        logger.info(f"Données sauvegardées dans {file_path}")

        return document

    async def process_html(self, url, depth):
        """
        Traite une page HTML et extrait son contenu et ses liens
        
        Args:
            url: URL de la page à traiter
            depth: Profondeur de l'URL dans l'arborescence
            
        Returns:
            Tuple (données extraites, nouvelles URLs)
        """
        logger.info(f"Traitement de la page HTML: {url}")
        
        page = await self.context.new_page()
        try:
            # Utiliser la méthode avec retry dans html_extractor.py
            await extract_page_content(page, url)
            
            # Extraire le titre
            title = await page.title()
            
            # Extraire le contenu principal
            content = await page.evaluate("""() => {
                // Essayer de trouver le contenu principal
                const mainContent = document.querySelector('main, #content, #main, .content, .main, article');
                
                if (mainContent) {
                    return mainContent.innerText;
                }
                
                // Fallback: utiliser le body si aucun contenu principal n'est trouvé
                return document.body.innerText;
            }""")
            
            # Extraire les métadonnées
            metadata = await page.evaluate("""() => {
                const meta = {};
                
                // Récupérer les balises meta
                const metaTags = document.querySelectorAll('meta');
                metaTags.forEach(tag => {
                    const name = tag.getAttribute('name') || tag.getAttribute('property');
                    const content = tag.getAttribute('content');
                    
                    if (name && content) {
                        meta[name] = content;
                    }
                });
                
                return meta;
            }""")
            
            # Extraire les titres h1, h2, h3
            headings = await page.evaluate("""() => {
                const headingElements = document.querySelectorAll('h1, h2, h3');
                return Array.from(headingElements).map(h => ({
                    level: parseInt(h.tagName.substring(1)),
                    text: h.innerText.trim()
                }));
            }""")
            
            # Extraire les liens
            links = await page.evaluate("""() => {
                const anchors = Array.from(document.querySelectorAll('a[href]'));
                return anchors.map(a => a.href);
            }""")
            
            # Filtrer les liens par domaine (bioforce.org) et patterns d'exclusion
            filtered_links = []
            for link in links:
                if link and not link.startswith('javascript:') and not link.startswith('#'):
                    # Convertir en URL absolue
                    full_url = urljoin(url, link)
                    parsed_url = urlparse(full_url)
                    
                    # Vérifier si le lien appartient au domaine bioforce.org
                    if parsed_url.netloc and "bioforce.org" in parsed_url.netloc:
                        # Vérifier les patterns d'exclusion
                        exclude = False
                        for pattern in EXCLUDE_PATTERNS:
                            if pattern in full_url:
                                exclude = True
                                break
                        
                        if not exclude:
                            filtered_links.append(full_url)
            
            # Prioriser les URLs
            new_urls = []
            for link in filtered_links:
                priority = prioritize_url(link, PRIORITY_PATTERNS)
                new_urls.append({
                    "url": link,
                    "priority": priority,
                    "depth": depth + 1
                })
            
            # Créer le document extrait
            data = {
                "url": url,
                "title": title,
                "content": content,
                "metadata": metadata,
                "headings": headings,
                "links": filtered_links,
                "timestamp": datetime.now().isoformat()
            }
            
            return data, new_urls
            
        except Exception as e:
            logger.error(f"Erreur lors du traitement de la page HTML {url}: {str(e)}")
            self.failed_urls.append(url)
            return None, []
            
        finally:
            await page.close()

    async def process_pdf(self, url):
        """
        Traite un fichier PDF et extrait son contenu
        
        Args:
            url: URL du PDF à traiter
            
        Returns:
            Données extraites ou None en cas d'erreur
        """
        logger.info(f"Traitement du PDF: {url}")
        
        try:
            # Télécharger le PDF
            os.makedirs(PDF_DIR, exist_ok=True)
            pdf_filename = os.path.basename(url)
            pdf_path = os.path.join(PDF_DIR, pdf_filename)
            
            # Utiliser une session HTTP pour télécharger le fichier
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.read()
                        with open(pdf_path, 'wb') as f:
                            f.write(content)
                    else:
                        logger.error(f"Impossible de télécharger le PDF {url}: {response.status}")
                        return None
            
            # Extraire le texte du PDF
            pdf_content = ""
            try:
                # Utiliser PyPDF2 ou PyMuPDF pour extraire le texte
                # Implémentation simplifiée pour cet exemple
                import pypdf
                with open(pdf_path, 'rb') as f:
                    reader = pypdf.PdfReader(f)
                    for page in reader.pages:
                        pdf_content += page.extract_text() + "\n"
            except Exception as e:
                logger.error(f"Erreur lors de l'extraction du texte du PDF {url}: {str(e)}")
            
            # Extraire le titre (du nom de fichier s'il n'est pas dans le PDF)
            title = os.path.splitext(pdf_filename)[0].replace('_', ' ').replace('-', ' ').title()
            
            # Créer le document extrait
            data = {
                "url": url,
                "title": title,
                "content": pdf_content,
                "pdf_path": pdf_path,
                "timestamp": datetime.now().isoformat()
            }
            
            return data
            
        except Exception as e:
            logger.error(f"Erreur lors du traitement du PDF {url}: {str(e)}")
            self.failed_urls.append(url)
            return None

async def main():
    """Fonction principale"""
    start_time = time.time()
    
    # Utiliser le scraper avec l'intégration du sitemap XML
    scraper = BioforceScraperMain(incremental=True)
    await scraper.run()
    
    end_time = time.time()
    duration = end_time - start_time
    
    logger.info(f"Temps d'exécution total: {duration:.2f} secondes")

if __name__ == "__main__":
    asyncio.run(main())
