"""
Script optimisé pour extraire et indexer l'ensemble des FAQ Bioforce de manière accélérée.
Utilise le traitement asynchrone et la parallélisation pour maximiser les performances.
"""
import os
import asyncio
import hashlib
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Set
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

from bioforce_scraper.config import QDRANT_COLLECTION, VECTOR_SIZE, LOG_DIR
from bioforce_scraper.utils.qdrant_connector import QdrantConnector
from bioforce_scraper.utils.embeddings import generate_embeddings
from bioforce_scraper.utils.logger import setup_logger

# Configuration du logger
log_file = os.path.join(LOG_DIR, f"faq_builder_accelerated_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
logger = setup_logger(__name__, log_file)

# URL de base pour les FAQ Bioforce
FAQ_BASE_URL = "https://www.bioforce.org/foire-aux-questions/"
FAQ_CATEGORIES = [
    "https://www.bioforce.org/foire-aux-questions/",
    "https://www.bioforce.org/foire-aux-questions/informations-generales-sur-les-formations/",
    "https://www.bioforce.org/foire-aux-questions/processus-de-selection/",
    "https://www.bioforce.org/foire-aux-questions/formations-qualifiantes-et-certifiantes/",
    "https://www.bioforce.org/foire-aux-questions/formations-en-e-learning/",
    "https://www.bioforce.org/foire-aux-questions/apres-la-formation/",
    "https://www.bioforce.org/foire-aux-questions/secteur-de-la-solidarite/",
]

# Nombre maximal de workers pour le traitement parallèle
MAX_WORKERS = 10
# Nombre maximal de requêtes HTTP simultanées
MAX_CONCURRENT_REQUESTS = 20
# Délai entre les requêtes (en secondes) pour éviter de surcharger le serveur
REQUEST_DELAY = 0.2
# Taille des batchs pour l'indexation
BATCH_SIZE = 10

class FastFaqBuilder:
    """
    Classe optimisée pour extraire et indexer rapidement les FAQ Bioforce
    """
    def __init__(self):
        self.qdrant = QdrantConnector(collection_name=QDRANT_COLLECTION, is_full_site=False)
        self.total_faq = 0
        self.discovered_faq = 0
        self.successful_faq = 0
        self.failed_faq = 0
        self.session = None
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        self.url_set = set()
        
    async def rebuild_collection(self):
        """
        Recrée la collection Qdrant et la remplit avec toutes les FAQ de Bioforce
        """
        logger.info("Début de la reconstruction accélérée de la collection BIOFORCE avec les FAQ...")
        start_time = datetime.now()
        
        # Recréer la collection
        self._recreate_collection()
        
        # Créer une session HTTP réutilisable
        async with aiohttp.ClientSession() as self.session:
            # Récupérer toutes les URLs de FAQ
            faq_urls = await self._discover_all_faq_urls()
            logger.info(f"Découvert {len(faq_urls)} URLs de FAQ à traiter")
            self.discovered_faq = len(faq_urls)
            
            # Traiter les FAQ par lots pour optimiser les performances
            await self._process_faq_urls_in_batches(faq_urls)
        
        # Afficher les statistiques
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        self._print_stats(duration)
        
        logger.info("Reconstruction accélérée de la collection terminée.")
        
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
    
    async def _discover_all_faq_urls(self) -> List[str]:
        """
        Récupère toutes les URLs de FAQ à partir des pages de catégories
        """
        all_urls = set()
        tasks = []
        
        # Extraire les URLs de FAQ depuis chaque page de catégorie
        for category_url in FAQ_CATEGORIES:
            tasks.append(self._extract_faq_urls_from_category(category_url))
        
        # Attendre que toutes les tâches soient terminées
        results = await asyncio.gather(*tasks)
        
        # Fusionner tous les résultats
        for urls in results:
            all_urls.update(urls)
        
        return list(all_urls)
    
    async def _extract_faq_urls_from_category(self, category_url: str) -> Set[str]:
        """
        Extrait toutes les URLs de FAQ d'une catégorie spécifique
        """
        async with self.semaphore:
            try:
                logger.info(f"Extraction des URLs depuis la catégorie: {category_url}")
                
                # Attendre un court délai pour éviter de surcharger le serveur
                await asyncio.sleep(REQUEST_DELAY)
                
                # Faire la requête
                async with self.session.get(category_url) as response:
                    if response.status != 200:
                        logger.error(f"Erreur {response.status} lors de l'accès à {category_url}")
                        return set()
                    
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Rechercher les liens de questions (plusieurs approches pour être robuste)
                    urls = set()
                    
                    # Approche 1: Liens contenus dans la zone de contenu principale
                    content_areas = soup.select('main, #content, .site-content, .entry-content, .post-content')
                    for area in content_areas:
                        for a_tag in area.find_all('a', href=True):
                            href = a_tag['href']
                            # Vérifier si c'est un lien de question
                            if '/question/' in href and href not in urls:
                                urls.add(href)
                    
                    # Approche 2: Tous les liens contenant '/question/'
                    if not urls:
                        for a_tag in soup.find_all('a', href=True):
                            href = a_tag['href']
                            if '/question/' in href:
                                urls.add(href)
                    
                    # S'assurer que toutes les URLs sont absolues
                    absolute_urls = {urljoin(category_url, url) if not url.startswith('http') else url for url in urls}
                    
                    logger.info(f"Trouvé {len(absolute_urls)} URL(s) de FAQ dans la catégorie {category_url}")
                    return absolute_urls
                
            except Exception as e:
                logger.error(f"Erreur lors de l'extraction des URLs de la catégorie {category_url}: {e}")
                return set()
    
    async def _process_faq_urls_in_batches(self, urls: List[str]):
        """
        Traite les URLs de FAQ par lots pour optimiser les performances
        """
        total = len(urls)
        for i in range(0, total, BATCH_SIZE):
            batch = urls[i:i+BATCH_SIZE]
            logger.info(f"Traitement du lot {i//BATCH_SIZE + 1}/{(total+BATCH_SIZE-1)//BATCH_SIZE} ({len(batch)} URLs)")
            
            # Traiter ce lot en parallèle
            tasks = [self._process_single_faq(url) for url in batch]
            await asyncio.gather(*tasks)
            
            # Attendre un court délai entre les lots pour éviter de surcharger les API
            await asyncio.sleep(0.5)
    
    async def _process_single_faq(self, url: str):
        """
        Traite une seule URL de FAQ: extraction, embedding et indexation
        """
        async with self.semaphore:
            self.total_faq += 1
            try:
                # Attendre un court délai pour éviter de surcharger le serveur
                await asyncio.sleep(REQUEST_DELAY)
                
                # Extraire le contenu de la FAQ
                faq_data = await self._extract_faq_content(url)
                
                if not faq_data:
                    logger.warning(f"Contenu non extrait pour {url}")
                    self.failed_faq += 1
                    return
                
                # Indexer la FAQ dans Qdrant
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
        try:
            logger.info(f"Extraction du contenu de la FAQ: {url}")
            
            # Récupérer le contenu HTML
            async with self.session.get(url) as response:
                if response.status != 200:
                    logger.error(f"Erreur {response.status} lors de l'accès à {url}")
                    return None
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Méthode améliorée pour extraire le titre et le contenu
                title = self._extract_faq_title(soup)
                content = self._extract_faq_answer(soup, url)
                
                if not title or not content or content == "Contenu non trouvé":
                    logger.warning(f"Extraction incomplète pour {url}: title={bool(title)}, content={bool(content)}")
                    category = self._determine_faq_category(url, soup)
                    
                    # Si l'extraction a échoué mais qu'on a pu déterminer la catégorie,
                    # on crée un contenu minimal
                    if category:
                        title = title or f"Question sur {category}"
                        content = content or f"Cette question concerne la catégorie {category} de Bioforce."
                    else:
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
            logger.error(f"Erreur lors de l'extraction de la FAQ {url}: {e}")
            return None
    
    def _extract_faq_title(self, soup: BeautifulSoup) -> str:
        """
        Extrait le titre (question) d'une page FAQ de manière robuste
        """
        # Approche 1: Balise H1
        h1_tags = soup.find_all('h1')
        if h1_tags:
            return h1_tags[0].get_text().strip()
        
        # Approche 2: Classes spécifiques
        title_elements = soup.select('.entry-title, .question-title, .faq-title, .dwqa-title')
        if title_elements:
            return title_elements[0].get_text().strip()
        
        # Approche 3: Extraction depuis l'URL
        match = re.search(r'/question/([^/]+)/?$', soup.current_url if hasattr(soup, 'current_url') else '')
        if match:
            # Convertir les tirets en espaces et capitaliser
            url_title = match.group(1).replace('-', ' ').capitalize()
            return url_title
        
        return "Question FAQ Bioforce"
    
    def _extract_faq_answer(self, soup: BeautifulSoup, url: str) -> str:
        """
        Extrait la réponse d'une page FAQ de manière robuste
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
                element.decompose()
            
            # Supprimer le titre pour ne garder que le contenu
            for h1 in main_content[0].find_all('h1'):
                h1.decompose()
            
            content = main_content[0].get_text().strip()
            if content:
                return content
        
        # Approche 3: Tout le contenu textuel de la page (dernier recours)
        body = soup.find('body')
        if body:
            # Supprimer les scripts, styles, navigation, header et footer
            for element in body.select('script, style, nav, header, footer'):
                element.decompose()
            
            content = body.get_text().strip()
            # Nettoyer le texte (supprimer les espaces multiples, les lignes vides)
            content = re.sub(r'\s+', ' ', content).strip()
            if content:
                return content
        
        # Fournir un contenu par défaut basé sur l'URL
        url_parts = url.split('/')
        if len(url_parts) > 4:
            topic = url_parts[-2].replace('-', ' ').capitalize()
            return f"Cette question concerne le sujet: {topic}. Veuillez consulter la FAQ Bioforce pour plus d'informations."
        
        return "Contenu non trouvé"
    
    def _determine_faq_category(self, url: str, soup: BeautifulSoup) -> str:
        """
        Détermine la catégorie d'une FAQ à partir de son URL ou du contenu de la page
        """
        # Extraction depuis l'URL
        category_patterns = {
            "formation": "Informations générales sur les formations",
            "selection": "Processus de sélection",
            "certifi": "Formations qualifiantes et certifiantes",
            "e-learning": "Formations en e-learning",
            "apres-la-formation": "Après la formation",
            "solidarite": "Secteur de la solidarité"
        }
        
        for pattern, category in category_patterns.items():
            if pattern in url:
                return category
        
        # Extraction depuis le contenu (breadcrumbs)
        breadcrumbs = soup.select('.breadcrumbs, .breadcrumb, .navigation-path')
        if breadcrumbs:
            text = breadcrumbs[0].get_text()
            for pattern, category in category_patterns.items():
                if pattern in text.lower():
                    return category
        
        return "FAQ Bioforce"
    
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
        logger.info("=== Statistiques de reconstruction des FAQ ===")
        logger.info(f"Total des FAQ découvertes: {self.discovered_faq}")
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
    logger.info(f"Début du processus de reconstruction FAQ accélérée: {start_time}")
    
    builder = FastFaqBuilder()
    await builder.rebuild_collection()
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    logger.info(f"Fin du processus de reconstruction: {end_time}")
    logger.info(f"Durée totale: {duration:.2f} secondes")

if __name__ == "__main__":
    asyncio.run(main())
