"""
Script optimisé pour indexer les FAQs de Bioforce en utilisant le fichier XML Sitemap.txt
Approche asynchrone pour maximiser les performances tout en respectant la structure existante
"""
import os
import re
import asyncio
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional, Set
import time

import aiohttp
from bs4 import BeautifulSoup

from bioforce_scraper.config import QDRANT_COLLECTION, VECTOR_SIZE, LOG_DIR
from bioforce_scraper.utils.qdrant_connector import QdrantConnector
from bioforce_scraper.utils.embeddings import generate_embeddings
from bioforce_scraper.utils.logger import setup_logger

# Configuration du logger
log_file = os.path.join(LOG_DIR, f"sitemap_faq_indexer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
logger = setup_logger(__name__, log_file)

# Chemin du fichier sitemap
SITEMAP_FILE = 'XML Sitemap.txt'

# Pattern pour identifier les URLs de questions
QUESTION_URL_PATTERN = r'https://www\.bioforce\.org/question/[^/\s]+'

# Configuration des performances
MAX_CONCURRENT_REQUESTS = 20  # Nombre maximal de requêtes HTTP simultanées
BATCH_SIZE = 10  # Taille des batchs pour l'indexation

class SitemapFaqIndexer:
    """
    Classe pour indexer les FAQs de Bioforce en utilisant le sitemap
    """
    def __init__(self):
        self.qdrant = QdrantConnector(collection_name=QDRANT_COLLECTION, is_full_site=False)
        self.total_faq = 0
        self.successful_faq = 0
        self.failed_faq = 0
        self.session = None
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        self.faq_urls = []
        
    async def run(self):
        """
        Exécute le processus complet d'extraction et d'indexation
        """
        start_time = datetime.now()
        logger.info(f"Début du processus d'indexation des FAQ depuis le sitemap: {start_time}")
        
        # Extraire les URLs du sitemap
        self.faq_urls = self._extract_faq_urls_from_sitemap()
        logger.info(f"Sitemap traité: {len(self.faq_urls)} URLs de FAQ extraites")
        
        if not self.faq_urls:
            logger.error("Aucune URL de FAQ trouvée dans le sitemap")
            return
        
        # Recréer la collection
        self._recreate_collection()
        
        # Créer une session HTTP réutilisable
        async with aiohttp.ClientSession() as self.session:
            # Indexer toutes les FAQ
            await self._index_all_faqs()
        
        # Afficher les statistiques
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        self._print_stats(duration)
        
        logger.info(f"Fin du processus d'indexation des FAQ: {end_time}")
        logger.info(f"Durée totale: {duration:.2f} secondes")
    
    def _extract_faq_urls_from_sitemap(self) -> List[str]:
        """
        Extrait les URLs des FAQ à partir du fichier sitemap
        """
        logger.info(f"Extraction des URLs depuis le fichier {SITEMAP_FILE}")
        
        faq_urls = []
        try:
            with open(SITEMAP_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Trouver toutes les URLs de questions
                matches = re.findall(QUESTION_URL_PATTERN, content)
                faq_urls = list(set(matches))  # Éliminer les doublons
                
                logger.info(f"Extraction réussie: {len(faq_urls)} URLs de FAQ trouvées")
                
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction des URLs depuis le sitemap: {e}")
        
        return faq_urls
        
    def _recreate_collection(self):
        """
        Supprime et recrée la collection Qdrant
        """
        logger.info(f"Recréation de la collection {QDRANT_COLLECTION}...")
        
        try:
            # Supprimer la collection si elle existe
            collections = self.qdrant.client.get_collections().collections
            collection_names = [c.name for c in collections]
            
            if QDRANT_COLLECTION in collection_names:
                logger.info(f"Suppression de la collection existante {QDRANT_COLLECTION}...")
                self.qdrant.client.delete_collection(collection_name=QDRANT_COLLECTION)
                
            # Créer la collection
            self.qdrant.ensure_collection(vector_size=VECTOR_SIZE)
            logger.info(f"Collection {QDRANT_COLLECTION} créée avec succès.")
            
        except Exception as e:
            logger.error(f"Erreur lors de la recréation de la collection {QDRANT_COLLECTION}: {e}")
            raise
    
    async def _index_all_faqs(self):
        """
        Indexe toutes les FAQ par batchs
        """
        logger.info(f"Début de l'indexation de {len(self.faq_urls)} FAQ...")
        
        # Traiter les URLs par lots
        for i in range(0, len(self.faq_urls), BATCH_SIZE):
            batch = self.faq_urls[i:i+BATCH_SIZE]
            logger.info(f"Traitement du lot {i//BATCH_SIZE + 1}/{(len(self.faq_urls)+BATCH_SIZE-1)//BATCH_SIZE}: {len(batch)} URLs")
            
            # Traiter ce lot en parallèle
            tasks = [self._process_and_index_faq(url) for url in batch]
            await asyncio.gather(*tasks)
            
            # Court délai entre les lots pour éviter de surcharger les API
            await asyncio.sleep(0.5)
        
        logger.info(f"Indexation terminée: {self.successful_faq}/{self.total_faq} réussies")
    
    async def _process_and_index_faq(self, url: str):
        """
        Traite et indexe une seule FAQ
        """
        self.total_faq += 1
        
        try:
            # Extraire le contenu
            faq_data = await self._extract_faq_content(url)
            if not faq_data:
                logger.warning(f"Contenu non extrait pour {url}")
                self.failed_faq += 1
                return
            
            # Indexer dans Qdrant
            success = await self._index_faq(faq_data)
            
            if success:
                self.successful_faq += 1
            else:
                self.failed_faq += 1
                
        except Exception as e:
            logger.error(f"Erreur lors du traitement de {url}: {e}")
            self.failed_faq += 1
    
    async def _extract_faq_content(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Extrait le contenu d'une page FAQ
        """
        async with self.semaphore:
            try:
                logger.info(f"Extraction du contenu de {url}")
                
                # Attendre un court délai pour éviter de surcharger le serveur
                await asyncio.sleep(0.2)
                
                async with self.session.get(url) as response:
                    if response.status != 200:
                        logger.warning(f"Erreur {response.status} lors de l'accès à {url}")
                        return None
                    
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Extraire le titre et le contenu
                    title = self._extract_title(soup, url)
                    content = self._extract_content(soup, url)
                    
                    if not title or not content or content == "Contenu non trouvé":
                        logger.warning(f"Extraction incomplète pour {url}: title={bool(title)}, content={bool(content)}")
                        return None
                    
                    # Préparer les données
                    faq_data = {
                        "title": title,
                        "content": content,
                        "url": url,
                        "timestamp": datetime.now().isoformat(),
                        "language": "fr", 
                        "category": "faq",
                        "content_type": "html",
                        "is_faq": True,
                        "relevance_score": 0.9
                    }
                    
                    logger.info(f"FAQ extraite avec succès: {title}")
                    return faq_data
                    
            except Exception as e:
                logger.error(f"Erreur lors de l'extraction de {url}: {e}")
                return None
    
    def _extract_title(self, soup: BeautifulSoup, url: str) -> str:
        """
        Extrait le titre (question) d'une page FAQ
        """
        # Approche 1: Balise H1
        h1_tags = soup.find_all('h1')
        if h1_tags and h1_tags[0].get_text().strip():
            return h1_tags[0].get_text().strip()
        
        # Approche 2: Classes spécifiques
        title_elements = soup.select('.entry-title, .question-title, .faq-title, .dwqa-title')
        if title_elements:
            return title_elements[0].get_text().strip()
        
        # Approche 3: Extraire depuis l'URL
        match = re.search(r'/question/([^/]+)/?$', url)
        if match:
            # Convertir les tirets en espaces et capitaliser
            url_title = match.group(1).replace('-', ' ').capitalize()
            return url_title
        
        return "Question FAQ Bioforce"
    
    def _extract_content(self, soup: BeautifulSoup, url: str) -> str:
        """
        Extrait la réponse d'une page FAQ
        """
        # Approche 1: Classes spécifiques pour les réponses FAQ
        content_elements = soup.select('.dwqa-answer-content, .answer-content, .faq-answer, .entry-content')
        if content_elements:
            content = content_elements[0].get_text().strip()
            if content:
                return content
        
        # Approche 2: Contenu principal après le titre
        main_content = soup.select('main, article, .site-main, .content-area')
        if main_content:
            # Supprimer les éléments de navigation et les sidebars
            for element in main_content[0].select('nav, .navigation, .sidebar, .widget-area, header, footer'):
                if element:
                    element.decompose()
            
            # Supprimer le titre pour ne garder que le contenu
            for h1 in main_content[0].find_all('h1'):
                if h1:
                    h1.decompose()
            
            content = main_content[0].get_text().strip()
            if content:
                # Nettoyer le contenu (espaces, sauts de ligne, etc.)
                content = re.sub(r'\s+', ' ', content).strip()
                return content
        
        # Approche 3: Tout le contenu textuel de la page (dernier recours)
        body = soup.find('body')
        if body:
            # Supprimer les scripts, styles, navigation, header et footer
            for element in body.select('script, style, nav, header, footer'):
                if element:
                    element.decompose()
            
            content = body.get_text().strip()
            # Nettoyer le texte
            content = re.sub(r'\s+', ' ', content).strip()
            if content:
                return content
        
        return "Contenu non trouvé"
    
    async def _index_faq(self, faq_item: Dict[str, Any]) -> bool:
        """
        Indexe un élément FAQ dans Qdrant
        """
        try:
            # Générer l'embedding
            embedding = await generate_embeddings(faq_item["content"])
            
            if not embedding:
                logger.error(f"Échec de génération d'embedding pour {faq_item['url']}")
                return False
            
            # Préparer les métadonnées
            payload = {
                "title": faq_item["title"],
                "content": faq_item["content"],
                "url": faq_item["url"],
                "source_url": faq_item["url"],
                "type": "html",
                "category": "faq",
                "timestamp": faq_item["timestamp"],
                "language": "fr",
                "relevance_score": 0.9,
                "is_faq": True
            }
            
            # Générer un ID unique basé sur l'URL
            doc_id = hashlib.md5(faq_item["url"].encode()).hexdigest()
            
            # Indexer dans Qdrant
            success = self.qdrant.upsert_document(id=doc_id, vector=embedding, payload=payload)
            if success:
                logger.info(f"FAQ indexée avec succès: {faq_item['title']}")
                return True
            else:
                logger.error(f"Échec de l'indexation pour: {faq_item['title']}")
                return False
            
        except Exception as e:
            logger.error(f"Erreur lors de l'indexation de la FAQ: {e}")
            return False
    
    def _print_stats(self, duration_seconds: float):
        """
        Affiche les statistiques de la reconstruction
        """
        logger.info("=== Statistiques d'indexation des FAQ ===")
        logger.info(f"Total des FAQ extraites du sitemap: {len(self.faq_urls)}")
        logger.info(f"Total des FAQ traitées: {self.total_faq}")
        logger.info(f"FAQ indexées avec succès: {self.successful_faq}")
        logger.info(f"FAQ échouées: {self.failed_faq}")
        logger.info(f"Taux de réussite: {(self.successful_faq / self.total_faq * 100) if self.total_faq > 0 else 0:.2f}%")
        logger.info(f"Durée totale: {duration_seconds:.2f} secondes")
        logger.info(f"Vitesse moyenne: {self.total_faq / duration_seconds:.2f} FAQ/seconde")
        logger.info("==============================================")

async def main():
    """Fonction principale"""
    start_time = datetime.now()
    logger.info(f"Début du processus d'indexation des FAQ depuis le sitemap: {start_time}")
    
    indexer = SitemapFaqIndexer()
    await indexer.run()
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    logger.info(f"Fin du processus: {end_time}")
    logger.info(f"Durée totale: {duration:.2f} secondes")

if __name__ == "__main__":
    asyncio.run(main())
