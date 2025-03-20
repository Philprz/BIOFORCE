"""
Module principal pour le scraper Bioforce
"""
import asyncio
# Imports non utilisés commentés plutôt que supprimés pour préserver la structure
# import base64
import hashlib  # Utilisé dans save_document_to_file pour générer des hashes
import json
# import logging
import os
# import random
# import re
import time
import uuid
from datetime import datetime
# Nettoyage des imports de typing en conservant seulement ceux utilisés
from urllib.parse import urlparse  # urljoin
import sys
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

import pathlib
# Ajouter le répertoire parent au path pour pouvoir importer les modules
sys.path.append(str(pathlib.Path(__file__).parent.parent))

# Nettoyage des imports inutilisés de config
from bioforce_scraper.config import (
    BASE_URL, EXCLUDE_EXTENSIONS, EXCLUDE_PATTERNS,
    LOG_FILE, MAX_PAGES, REQUEST_DELAY, USER_AGENT,
    DATA_DIR, START_URLS, FAQ_URLS, FAQ_PATTERNS, FAQ_INDEX_URLS, FAQ_SITEMAP_URL,
    PRIORITY_PATTERNS, PDF_DIR,  # PDF_DIR est utilisé dans la fonction download_file
    # API_HOST, COLLECTION_NAME, MAX_RETRIES, MAX_TIMEOUT, OUTPUT_DIR, 
    # RETRY_DELAY, QDRANT_URL, QDRANT_API_KEY, 
    CONCURRENT_REQUESTS,  # Nombre maximal de requêtes concurrentes
    PROCESSED_URLS_FILE  # Fichier pour stocker les URLs précédemment traitées
)
from bioforce_scraper.extractors.html_extractor import extract_metadata, clean_text
from bioforce_scraper.extractors.pdf_extractor import extract_text_from_pdf
# from bioforce_scraper.extractors.pdf_extractor import extract_text_from_pdf
from bioforce_scraper.utils.content_classifier import ContentClassifier
from bioforce_scraper.utils.logger import setup_logger
from bioforce_scraper.utils.robots_parser import RobotsParser
from bioforce_scraper.utils.sitemap_parser import SitemapParser
from bioforce_scraper.utils.content_tracker import ContentTracker
from bioforce_scraper.utils.embeddings import generate_embeddings
from bioforce_scraper.utils.qdrant_connector import QdrantConnector
from bioforce_scraper.utils.url_prioritizer import prioritize_url
from bioforce_scraper.integration.gpt_filter_integration import GPTFilterIntegration
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
        self.content_classifier = ContentClassifier()  # Initialisation du classifieur de contenu
        self.content_tracker = ContentTracker()  # Initialisation du tracker de contenu
        self.gpt_filter = GPTFilterIntegration()  # Initialisation du filtre GPT
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
        # Vérifier que la méthode is_allowed est bien présente
        if not hasattr(self.robots_parser, 'is_allowed'):
            # Si la méthode n'est pas disponible, définir une méthode par défaut
            logger.warning("La méthode is_allowed n'est pas définie dans RobotsParser, utilisation d'une méthode par défaut")
            self.robots_parser.is_allowed = lambda url: True
        await self.robots_parser.load()
        
        # Initialisation de Playwright
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 800}
        )
        
        # En mode incrémental, charger les URLs déjà connues
        if self.incremental and self.content_classifier:
            known_urls = set(self.content_classifier.get_all_tracked_urls())
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
        """
        Exécute le processus de scraping
        """
        try:
            # Tester la connexion à Qdrant et la génération d'embeddings
            if not await self.test_qdrant_and_embedding():
                logger.error("Échec des tests préliminaires, arrêt du traitement")
                return
            
            # Initialiser le navigateur
            await self.initialize()
            
            logger.info("Démarrage du scraping...")
            processed_count = 0
            batch_count = 0
            
            # Créer le répertoire de données s'il n'existe pas
            os.makedirs(DATA_DIR, exist_ok=True)
            
            # Récupérer les URLs FAQ depuis le sitemap XML
            logger.info("Récupération des URLs FAQ depuis le sitemap...")
            faq_urls_with_dates = {}
            
            # Utiliser le SitemapParser pour récupérer les URLs FAQ avec leurs dates de dernière modification
            sitemap_parser = SitemapParser()
            faq_urls_with_dates = await sitemap_parser.parse_faq_sitemap(FAQ_SITEMAP_URL)
            
            if not faq_urls_with_dates:
                logger.warning("Aucune URL FAQ trouvée dans le sitemap. Utilisation de l'approche classique.")
                # Ajouter les URLs FAQ directement depuis la configuration
                for url in FAQ_URLS:
                    self.queue.append({"url": url, "priority": 100, "depth": 0, "is_faq": True})
                logger.info(f"Ajout prioritaire des {len(FAQ_URLS)} URLs de la FAQ")
                
                # Explorer les pages index de FAQ pour trouver toutes les questions
                await self.explore_faq_pages()
            else:
                logger.info(f"{len(faq_urls_with_dates)} URLs FAQ trouvées dans le sitemap.")
                
                # Stocker les timestamps des documents déjà traités pour décider quoi mettre à jour
                processed_doc_timestamps = {}
                if self.incremental:
                    # Récupérer les informations des documents déjà traités
                    for file_name in os.listdir(DATA_DIR):
                        if file_name.endswith('.json'):
                            try:
                                file_path = os.path.join(DATA_DIR, file_name)
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    doc_data = json.load(f)
                                    url = doc_data.get('url', '')
                                    timestamp = doc_data.get('timestamp', '')
                                    if url and timestamp:
                                        processed_doc_timestamps[url] = timestamp
                            except Exception as e:
                                logger.error(f"Erreur lors du chargement du document existant {file_name}: {e}")
                
                # Ajouter les URLs FAQ à la queue en fonction de leur date de dernière modification
                faq_added = 0
                for url, lastmod in faq_urls_with_dates.items():
                    # Vérifier si l'URL a déjà été traitée et si elle a été modifiée depuis
                    needs_update = True
                    if self.incremental and url in processed_doc_timestamps:
                        stored_timestamp = processed_doc_timestamps[url]
                        
                        # Comparer les dates
                        try:
                            # Convertir lastmod en datetime
                            if 'T' in lastmod:
                                # Gérer les cas avec timezone +00:00
                                if '+' in lastmod:
                                    lastmod_dt = datetime.strptime(lastmod.split('+')[0], '%Y-%m-%dT%H:%M:%S')
                                else:
                                    lastmod_dt = datetime.strptime(lastmod, '%Y-%m-%dT%H:%M:%S')
                            else:
                                lastmod_dt = datetime.strptime(lastmod, '%Y-%m-%d')
                            
                            # Convertir stored_timestamp en datetime
                            if 'T' in stored_timestamp:
                                # Gérer les cas avec timezone +00:00
                                if '+' in stored_timestamp:
                                    stored_dt = datetime.strptime(stored_timestamp.split('+')[0], '%Y-%m-%dT%H:%M:%S')
                                else:
                                    stored_dt = datetime.strptime(stored_timestamp, '%Y-%m-%dT%H:%M:%S.%f')
                            else:
                                stored_dt = datetime.strptime(stored_timestamp, '%Y-%m-%d')
                            
                            # Si la date stockée est plus récente, pas besoin de mettre à jour
                            if stored_dt >= lastmod_dt:
                                needs_update = False
                                logger.debug(f"FAQ déjà à jour, ignorée: {url}")
                        except Exception as e:
                            logger.warning(f"Erreur lors de la comparaison des dates pour {url}: {e}")
                    
                    if needs_update and url not in self.visited_urls:
                        self.queue.append({"url": url, "priority": 100, "depth": 0, "is_faq": True, "lastmod": lastmod})
                        faq_added += 1
                
                logger.info(f"{faq_added} URLs FAQ ajoutées à la file d'attente pour traitement")
            
            # Initialiser la file d'attente avec les URLs de départ
            if not self.queue:
                self.queue = [
                    {"url": BASE_URL, "priority": 100, "depth": 0}
                ]
                
                # Charger les URLs FAQ en priorité (si applicable)
                await self.explore_faq_pages()
            
            # Charger les documents précédemment traités (pour le mode incrémental)
            processed_doc_timestamps = {}
            if self.incremental and os.path.exists(PROCESSED_URLS_FILE):
                try:
                    with open(PROCESSED_URLS_FILE, 'r') as f:
                        processed_doc_timestamps = json.load(f)
                    logger.info(f"Chargement de {len(processed_doc_timestamps)} URLs précédemment traitées")
                except Exception as e:
                    logger.error(f"Erreur lors du chargement des URLs précédemment traitées: {e}")
            
            # Stocker les URLs déjà visitées avant cette exécution 
            # pour ne pas les compter dans la limite MAX_PAGES
            previously_visited_urls = set()
            if self.incremental:
                previously_visited_urls = set(processed_doc_timestamps.keys())
                logger.info(f"{len(previously_visited_urls)} URLs précédemment visitées ne seront pas comptées dans la limite MAX_PAGES")
            
            # Traiter la file d'attente jusqu'à ce qu'elle soit vide ou qu'on atteigne la limite
            while self.queue and processed_count < MAX_PAGES:
                # Trier la file d'attente par priorité
                self.queue.sort(key=lambda x: x.get('priority', 0), reverse=True)
                
                # Déterminer combien d'URLs traiter en parallèle
                # Limiter le nombre en fonction des URLs restantes et de la limite MAX_PAGES
                batch_size = min(
                    CONCURRENT_REQUESTS,  # Nombre maximal de requêtes concurrentes
                    len(self.queue),      # Nombre d'URLs dans la file d'attente
                    MAX_PAGES - processed_count  # Nombre de pages restantes avant d'atteindre la limite
                )
                
                if batch_size <= 0:
                    break
                
                # Extraire un lot d'URLs à traiter en parallèle
                batch_urls = []
                batch_info = []
                
                for _ in range(batch_size):
                    if not self.queue:
                        break
                        
                    url_info = self.queue.pop(0)
                    url = url_info.get("url")
                    
                    # Vérifier si l'URL est déjà dans les URLs visitées
                    if url in self.visited_urls:
                        continue
                        
                    # Vérifier le robots.txt
                    if not self.robots_parser.is_allowed(url):
                        logger.info(f"URL {url} non autorisée par robots.txt, ignorée")
                        continue
                        
                    # Vérification du mode incrémental
                    if self.incremental and url in processed_doc_timestamps:
                        lastmod = url_info.get("lastmod", None)
                        if lastmod:
                            stored_timestamp = processed_doc_timestamps[url]
                            
                            # Comparer les dates
                            try:
                                # Convertir lastmod en datetime
                                if 'T' in lastmod:
                                    # Gérer les cas avec timezone +00:00
                                    if '+' in lastmod:
                                        lastmod_dt = datetime.strptime(lastmod.split('+')[0], '%Y-%m-%dT%H:%M:%S')
                                    else:
                                        lastmod_dt = datetime.strptime(lastmod, '%Y-%m-%dT%H:%M:%S')
                                else:
                                    lastmod_dt = datetime.strptime(lastmod, '%Y-%m-%d')
                                
                                # Convertir stored_timestamp en datetime
                                if 'T' in stored_timestamp:
                                    # Gérer les cas avec timezone +00:00
                                    if '+' in stored_timestamp:
                                        stored_dt = datetime.strptime(stored_timestamp.split('+')[0], '%Y-%m-%dT%H:%M:%S')
                                    else:
                                        stored_dt = datetime.strptime(stored_timestamp, '%Y-%m-%dT%H:%M:%S.%f')
                                else:
                                    stored_dt = datetime.strptime(stored_timestamp, '%Y-%m-%d')
                                
                                # Si la date stockée est plus récente, pas besoin de mettre à jour
                                if stored_dt >= lastmod_dt:
                                    logger.info(f"URL déjà à jour, ignorée: {url}")
                                    self.skipped_count += 1
                                    continue
                                else:
                                    logger.info(f"URL modifiée, re-scraping: {url}")
                            except Exception as e:
                                logger.warning(f"Erreur lors de la comparaison des dates pour {url}: {e}")
                    
                    # Ajouter l'URL au lot à traiter
                    batch_urls.append(url)
                    batch_info.append(url_info)
                
                if not batch_urls:
                    continue
                
                logger.info(f"Traitement parallèle de {len(batch_urls)} URLs")
                
                # Marquer les URLs comme visitées avant traitement pour éviter les doublons
                for url in batch_urls:
                    self.visited_urls.add(url)
                    # N'incrémenter le compteur que pour les nouvelles URLs (non visitées précédemment)
                    if url not in previously_visited_urls:
                        processed_count += 1
                    else:
                        logger.debug(f"URL déjà visitée dans une exécution précédente, non comptée: {url}")
                
                # Créer les tâches pour le traitement asynchrone
                tasks = []
                for i, url_info in enumerate(batch_info):
                    url = batch_urls[i]
                    depth = url_info.get("depth", 0)
                    
                    if url.endswith('.pdf'):
                        tasks.append(self.process_pdf(url))
                    else:
                        tasks.append(self.process_html(url, depth))
                
                # Exécuter les tâches en parallèle
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Traiter les résultats
                new_batch_count = 0
                for i, result in enumerate(results):
                    url = batch_urls[i]
                    
                    # Vérifier si une exception s'est produite
                    if isinstance(result, Exception):
                        logger.error(f"Erreur lors du traitement de {url}: {result}")
                        continue
                    
                    # Traiter le résultat en fonction du type d'URL
                    if url.endswith('.pdf'):
                        data = result
                        if data:
                            self.pdf_count += 1
                            # Sauvegarder le document PDF
                            data_to_index = self.save_data(data)
                            if data_to_index:
                                self.doc_batch.append(data_to_index)
                                new_batch_count += 1
                    else:
                        data, new_urls = result
                        if data:
                            self.html_count += 1
                            # Sauvegarder le document HTML
                            data_to_index = self.save_data(data)
                            if data_to_index:
                                self.doc_batch.append(data_to_index)
                                new_batch_count += 1
                            
                            # Ajouter les nouvelles URLs à la file d'attente
                            for new_url_info in new_urls:
                                if new_url_info.get("url") not in self.visited_urls:
                                    self.queue.append(new_url_info)
                
                # Mettre à jour le compteur de batch
                batch_count += new_batch_count
                
                # Afficher des statistiques intermédiaires tous les 100 URLs visitées
                if len(self.visited_urls) % 100 == 0:
                    acceptance_rate = (self.html_count + self.pdf_count) / len(self.visited_urls) * 100 if self.visited_urls else 0
                    logger.info(f"Progression: {len(self.visited_urls)} URLs visitées, {self.html_count + self.pdf_count} indexées ({acceptance_rate:.1f}% d'acceptation)")
                
                # Indexer si le lot est suffisamment grand
                if batch_count >= self.batch_size:
                    logger.info(f"Indexation d'un lot de {batch_count} documents dans Qdrant...")
                    await self.batch_index_to_qdrant()
                    batch_count = 0
                
                # Pause courte entre les lots pour éviter de surcharger le serveur
                await asyncio.sleep(REQUEST_DELAY / 2)
            
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
        
        logger.info(f"Indexation d'un lot de {len(self.doc_batch)} documents dans Qdrant...")
        
        _success_count = 0  # Préfixé avec _ car non utilisé
        error_count = 0
        indexed_count = 0
        faq_count = 0
        regular_count = 0
        
        for document in self.doc_batch:
            try:
                # Générer un ID unique pour le document s'il n'en a pas déjà un
                _doc_id = document.get("doc_id", str(uuid.uuid4()))  # Préfixé avec _ car non utilisé
                
                # Générer les embeddings pour le contenu
                content_to_embed = f"{document['title']} {document['content']}"
                if document.get('pdf_content'):
                    content_to_embed += f" {document['pdf_content']}"
                
                embedding = await generate_embeddings(content_to_embed)
                
                # Vérifier si c'est un document FAQ
                url = document["url"]
                is_faq = document.get("is_faq", False) or any(pattern in url for pattern in FAQ_PATTERNS)
                
                # Créer le payload pour Qdrant
                payload = {
                    "source_url": url,
                    "title": document["title"],
                    "content": document["content"],
                    "category": document["category"],
                    "timestamp": document.get("timestamp", ""),
                    "language": document.get("language", "fr"),
                    "relevance_score": document.get("relevance_score", 0.5),
                    "type": "html" if not document.get("pdf_path") else "pdf",
                    "is_faq": is_faq,
                    "vector": embedding if embedding else None
                }
                
                # Ajouter le document à Qdrant
                if is_faq:
                    # Les documents FAQ vont UNIQUEMENT dans la collection BIOFORCE
                    logger.info(f"Indexation document FAQ dans la collection BIOFORCE: {url}")
                    self.qdrant_connector.collection_name = "BIOFORCE"
                    result = self.qdrant_connector.upsert_document_chunks(payload, generate_id=True)
                    if result:
                        faq_count += 1
                        indexed_count += 1
                else:
                    # Les documents NON-FAQ vont UNIQUEMENT dans BIOFORCE_ALL
                    logger.info(f"Indexation document dans la collection BIOFORCE_ALL: {url}")
                    self.qdrant_connector.collection_name = "BIOFORCE_ALL"
                    result = self.qdrant_connector.upsert_document_chunks(payload, generate_id=True)
                    if result:
                        regular_count += 1
                        indexed_count += 1
                
                if not result:
                    error_count += 1
                    logger.error(f"Erreur lors de l'indexation dans Qdrant: {url}")
                
            except Exception as e:
                error_count += 1
                logger.error(f"Erreur lors de l'indexation dans Qdrant: {str(e)}")
        
        self.doc_batch = []  # Vider le batch après traitement
        self.batch_count += 1
        
        # Journalisation des résultats
        if indexed_count > 0:
            logger.info(f"Lot {self.batch_count} indexé avec succès: {indexed_count} documents ({faq_count} FAQ, {regular_count} standards)")
        if error_count > 0:
            logger.warning(f"Erreurs d'indexation dans le lot {self.batch_count}: {error_count} documents")

    async def test_qdrant_and_embedding(self):
        """
        Teste la connexion à Qdrant et la génération d'embeddings au début du processus
        
        Returns:
            bool: True si le test est réussi, False sinon
        """
        logger.info("Test de la connexion à Qdrant et de la génération d'embeddings...")
        try:
            # Test de génération d'embeddings
            test_text = "Ceci est un test de génération d'embeddings pour Bioforce"
            embedding = await generate_embeddings(test_text)
            
            if embedding is None:
                logger.error("Échec du test de génération d'embeddings")
                return False
            
            logger.info(f"Test de génération d'embeddings réussi (dimension: {len(embedding)})")
            
            # Test d'upsert dans Qdrant
            test_doc = {
                "source_url": "https://www.bioforce.org/test",
                "title": "Test Document",
                "content": test_text,
                "category": "test",
                "type": "html",
                "language": "fr",
                "vector": embedding
            }
            
            # Test d'upsert dans Qdrant (collection BIOFORCE_ALL)
            result_all = self.qdrant_connector.upsert_document_chunks(test_doc)
            if not result_all:
                logger.error("Échec du test d'upsert dans la collection BIOFORCE_ALL")
                return False
            
            # Test d'upsert dans Qdrant (collection BIOFORCE)
            test_doc["source_url"] = "https://www.bioforce.org/question/test"
            result_faq = self.qdrant_connector.upsert_document_chunks(test_doc)
            if not result_faq:
                logger.error("Échec du test d'upsert dans la collection BIOFORCE")
                return False
            
            logger.info("Test de connexion à Qdrant et d'upsert de documents réussi")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors du test de Qdrant et des embeddings: {str(e)}")
            return False

    def save_data(self, url_data):
        """Sauvegarde les données extraites"""
        url = url_data.get("url", "")
        content = url_data.get("content", "")
        title = url_data.get("title", "")
        timestamp = url_data.get("timestamp", datetime.now().isoformat())  # Utiliser le timestamp actuel s'il n'est pas défini
        _links = url_data.get("links", [])  # Préfixé avec _ car non utilisé
        _pdf_links = url_data.get("pdf_links", [])  # Préfixé avec _ car non utilisé
        _other_links = url_data.get("other_links", [])  # Préfixé avec _ car non utilisé
        pdf_content = url_data.get("pdf_content", "")
        pdf_path = url_data.get("pdf_path", "")
        language = 'fr'  # Langue par défaut (français)

        # Vérifier si le contenu est pertinent pour l'indexation
        if not self.content_classifier.should_index_content(url_data):
            logger.info(f"Contenu non pertinent, ignoré pour l'indexation: {url}")
            self.skipped_count += 1  # Incrémenter le compteur de pages ignorées
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
        # Utiliser un hash de l'URL comme identifiant de base, plus stable pour les mises à jour
        doc_id = hashlib.md5(url.encode()).hexdigest()
       
        # Si le contenu a un timestamp, l'ajouter à l'ID pour suivre les mises à jour
        current_time = datetime.now().strftime("%Y-%m-%dT%H-%M-%S.%f")
        file_id = f"{doc_id}_{current_time}"

        # Archiver les données extraites
        os.makedirs(DATA_DIR, exist_ok=True)
        file_path = os.path.join(DATA_DIR, f"{file_id}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(document, f, ensure_ascii=False, indent=2)
        logger.info(f"Données sauvegardées dans {file_path}")

        # Incrémenter le compteur de nouveaux contenus
        self.new_content_count += 1
        
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
        logger.info(f"Traitement de {url}")
        
        # Vérifier si l'URL a déjà été scrapée
        if self.incremental and url in self.visited_urls:
            logger.info(f"URL déjà visitée, ignorée: {url}")
            return None, []
        
        # Ajouter l'URL à la liste des URLs visitées
        self.visited_urls.add(url)
        
        page = await self.context.new_page()
        try:
            # Accéder à la page
            await page.goto(url, wait_until="networkidle")
            
            # Vérifier si c'est une page FAQ (en utilisant l'URL et le contenu)
            is_faq = any(pattern in url for pattern in FAQ_PATTERNS)
            
            # Vérifier également le contenu de la page pour des indicateurs de FAQ
            if not is_faq:
                # Rechercher des éléments typiques des pages FAQ dans le contenu
                faq_indicators = await page.evaluate("""() => {
                    // Vérifier des schémas courants dans les pages FAQ
                    const hasQuestionTitle = !!document.querySelector('h1, h2, h3').textContent.includes('?');
                    const hasQuestionSections = document.querySelectorAll('h2, h3, .question, .faq-question').length > 0;
                    const hasFaqClasses = !!document.querySelector('.faq, .question, .answer, .qa, .accordion');
                    const hasQuestionMark = document.body.textContent.split('?').length > 3; // Plusieurs points d'interrogation
                    
                    return {
                        hasQuestionTitle,
                        hasQuestionSections,
                        hasFaqClasses,
                        hasQuestionMark
                    };
                }""")
                
                # Considérer comme FAQ si plusieurs indicateurs sont présents
                is_faq = (faq_indicators.get('hasQuestionTitle', False) and faq_indicators.get('hasQuestionMark', False)) or \
                         (faq_indicators.get('hasQuestionSections', False) and faq_indicators.get('hasFaqClasses', False))
                
                if is_faq:
                    logger.info(f"Page identifiée comme FAQ par analyse de contenu: {url}")
            
            # Obtenir le contenu HTML
            html_content = await page.content()
            
            # Extraire le contenu de la page
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extraction des données manuellement
            content_data = {
                "url": url,
                "title": soup.title.text.strip() if soup.title else "",
                "content": clean_text(soup.get_text()),
                "timestamp": datetime.now().isoformat(),
                "is_faq": is_faq,
                "relevance_score": 0.7,  # Score de base
            }
            
            # Ajout des métadonnées
            metadata = extract_metadata(soup)
            content_data.update(metadata)
            
            # Analyse avec le classifieur si disponible
            if self.content_classifier:
                # Obtenir les résultats de classification
                is_relevant, relevance_score, category = self.content_classifier.classify_content(content_data)
                content_data["relevance_score"] = relevance_score
                content_data["category"] = category
            
            if not content_data:
                logger.warning(f"Aucun contenu extrait pour {url}")
                return None, []
            
            # Si c'est une FAQ, augmenter le score de pertinence
            if is_faq:
                content_data["relevance_score"] = max(content_data.get("relevance_score", 0.5), 0.9)
                logger.info(f"Traitement d'une page FAQ: {url}")
            
            # Filtrage intelligent par GPT pour améliorer la qualité des données
            filtered_content = await self.gpt_filter.process_html_content(content_data)
            
            # Ne continuer que si le contenu n'a pas été filtré
            if filtered_content:
                # Extraire les liens de la page
                links = []
                for a_tag in soup.find_all('a', href=True):
                    href = a_tag['href']
                    # Traiter les URLs relatives
                    if href.startswith('/'): 
                        href = f"{BASE_URL}{href}"
                    elif not href.startswith(('http://', 'https://')):
                        continue
                    
                    # Vérifier si l'URL appartient au domaine
                    parsed_href = urlparse(href)
                    if not parsed_href.netloc or "bioforce.org" not in parsed_href.netloc:
                        continue
                    
                    # Vérifier les patterns d'exclusion
                    exclude = False
                    for pattern in EXCLUDE_PATTERNS:
                        if pattern in href:
                            exclude = True
                            break
                    
                    # Vérifier les extensions exclues
                    for ext in EXCLUDE_EXTENSIONS:
                        if href.endswith(ext):
                            if ext == '.pdf':
                                # Ajouter les PDFs à la file pour traitement
                                links.append({"url": href, "priority": 50, "depth": depth + 1, "is_pdf": True, "is_faq": is_faq})
                            exclude = True
                            break
                    
                    if exclude:
                        continue
                    
                    # Vérifier si c'est une URL de FAQ
                    link_is_faq = any(pattern in href for pattern in FAQ_PATTERNS)
                    
                    # Calculer la priorité de l'URL
                    priority = 10  # Priorité de base
                    if prioritize_url(href, PRIORITY_PATTERNS):
                        priority = 50  # Priorité élevée pour les URLs importantes
                    
                    # Augmenter significativement la priorité si c'est une URL de FAQ
                    if link_is_faq:
                        priority = 100  # Priorité maximale pour les FAQs
                    
                    # Augmenter la priorité des liens trouvés dans une page FAQ
                    if is_faq and not link_is_faq:
                        priority += 20  # Les liens trouvés dans des pages FAQ sont aussi importants
                    
                    links.append({"url": href, "priority": priority, "depth": depth + 1, "is_faq": link_is_faq})
                
                return filtered_content, links
            
            else:
                logger.info(f"Contenu filtré, ignoré: {url}")
                return None, []
            
        except Exception as e:
            logger.error(f"Erreur lors du traitement de {url}: {e}")
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
            response = await self.download_file(url)
            if not response:
                logger.error(f"Impossible de télécharger le PDF: {url}")
                return None
                
            # Extraire le contenu du PDF
            pdf_content = await extract_text_from_pdf(response)
            
            if not pdf_content:
                logger.error(f"Impossible d'extraire le contenu du PDF: {url}")
                return None
                
            # Préparer les métadonnées
            filename = os.path.basename(url)
            title = os.path.splitext(filename)[0].replace('-', ' ').replace('_', ' ').title()
            
            pdf_data = {
                "url": url,
                "title": title,
                "content": pdf_content,
                "content_type": "pdf",
                "date_extraction": datetime.now().strftime("%Y-%m-%d"),
                "source": "bioforce",
                "relevance_score": 0.8  # Les PDFs sont généralement très pertinents
            }
            
            # Filtrage intelligent par GPT pour améliorer la qualité des données
            filtered_content, is_useful = await self.gpt_filter.process_pdf_content(pdf_data)
            
            # Ne continuer que si le contenu est utile
            if not is_useful:
                logger.info(f"Contenu PDF filtré, ignoré: {url}")
                return None
                
            # Sauvegarder les données
            document = await self.save_data(filtered_content)
            
            # Incrémenter le compteur de PDFs
            self.pdf_count += 1
            
            return document
                
        except Exception as e:
            logger.error(f"Erreur lors du traitement du PDF {url}: {e}")
            return None

    async def download_file(self, url):
        """
        Télécharge un fichier depuis une URL
        
        Args:
            url: URL du fichier à télécharger
            
        Returns:
            Le contenu du fichier ou None en cas d'erreur
        """
        logger.info(f"Téléchargement du fichier: {url}")
        
        try:
            # Créer le répertoire PDF si nécessaire
            os.makedirs(PDF_DIR, exist_ok=True)
            
            # Configurer une nouvelle page
            page = await self.context.new_page()
            try:
                # Intercepter la réponse
                response = await page.goto(url, wait_until="domcontentloaded")
                
                if response and response.status == 200:
                    # Récupérer le contenu
                    content = await response.body()
                    return content
                else:
                    status_code = response.status if response else "inconnu"
                    logger.error(f"Échec du téléchargement: {url} (Code: {status_code})")
                    return None
            finally:
                await page.close()
                
        except Exception as e:
            logger.error(f"Erreur lors du téléchargement de {url}: {e}")
            return None

    async def explore_faq_pages(self):
        """
        Explore spécifiquement les pages FAQ pour les ajouter à la file d'attente en priorité
        Cette fonction parcourt systématiquement les pages index de FAQ pour trouver toutes les questions
        """
        logger.info("Exploration dédiée des pages FAQ...")
        
        # Initialiser un ensemble pour éviter les doublons
        faq_urls = set()
        
        # Explorer chaque page index de FAQ
        for index_url in FAQ_INDEX_URLS:
            logger.info(f"Exploration de la page index FAQ: {index_url}")
            
            page = await self.context.new_page()
            try:
                # Accéder à la page d'index de FAQ
                await page.goto(index_url, wait_until="networkidle")
                
                # Extraire tous les liens
                links = await page.evaluate("""() => {
                    const anchors = Array.from(document.querySelectorAll('a[href]'));
                    return anchors.map(a => a.href);
                }""")
                
                # Filtrer les liens pour ne garder que les questions FAQ
                for link in links:
                    # Vérifier si le lien est une page de question FAQ
                    if link and isinstance(link, str) and any(pattern in link for pattern in FAQ_PATTERNS):
                        # Vérifier que l'URL est du domaine bioforce.org
                        parsed_url = urlparse(link)
                        if parsed_url.netloc and "bioforce.org" in parsed_url.netloc:
                            # Vérifier les patterns d'exclusion
                            exclude = False
                            for pattern in EXCLUDE_PATTERNS:
                                if pattern in link:
                                    exclude = True
                                    break
                            
                            if not exclude and link not in faq_urls:
                                faq_urls.add(link)
                                logger.info(f"URL FAQ trouvée: {link}")
            
            except Exception as e:
                logger.error(f"Erreur lors de l'exploration de la page FAQ {index_url}: {str(e)}")
            
            finally:
                await page.close()
        
        # Ajouter toutes les URLs FAQ à la file d'attente avec une priorité maximale
        faq_count = 0
        for url in faq_urls:
            if url not in self.visited_urls:
                self.queue.append({"url": url, "priority": 100, "depth": 0, "is_faq": True})
                faq_count += 1
        
        logger.info(f"Exploration FAQ terminée: {faq_count} URLs de FAQ ajoutées à la file d'attente")
        return faq_count

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
