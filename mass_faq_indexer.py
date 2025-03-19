"""
Script optimisé pour extraire et indexer en masse toutes les FAQ de Bioforce
Utilise une approche basée sur la recherche du site et le traitement parallèle
"""
import os
import re
import asyncio
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional, Set
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup

from bioforce_scraper.config import QDRANT_COLLECTION, VECTOR_SIZE, LOG_DIR
from bioforce_scraper.utils.qdrant_connector import QdrantConnector
from bioforce_scraper.utils.embeddings import generate_embeddings
from bioforce_scraper.utils.logger import setup_logger

# Configuration du logger
log_file = os.path.join(LOG_DIR, f"mass_faq_indexer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
logger = setup_logger(__name__, log_file)

# Base du site Bioforce
BIOFORCE_BASE_URL = "https://www.bioforce.org"

# Modèle des URLs de questions
QUESTION_URL_PATTERN = r'https://www\.bioforce\.org/question/[^/]+/?$'

# Nombre maximal de requêtes HTTP simultanées
MAX_CONCURRENT_REQUESTS = 20

# Liste des URLs de FAQ que nous avons déjà identifiées
KNOWN_FAQ_URLS = [
    "https://www.bioforce.org/question/sed-ut-perspiciatis-unde-omnis-iste-natus-error-sit-voluptatem-accusantium-doloremque-laudantium-totam-rem-2/",
    "https://www.bioforce.org/question/quelle-est-la-specificite-des-formations-bioforce/",
    "https://www.bioforce.org/question/qui-sont-les-intervenants-formateurs-de-bioforce/",
    "https://www.bioforce.org/question/quels-sont-les-parcours-profils-des-formateurs/",
    "https://www.bioforce.org/question/comment-fonctionne-le-cpf-de-transition-professionnelle-anciennement-cif/",
    "https://www.bioforce.org/question/les-supports-de-cours-me-sont-ils-communiques/",
    "https://www.bioforce.org/question/comment-venir-jusquau-lieu-de-formation/",
    "https://www.bioforce.org/question/quest-ce-quune-formation-bioforce-en-e-learning/",
    "https://www.bioforce.org/question/quest-ce-que-biomoodle/",
    "https://www.bioforce.org/question/quelle-est-la-difference-entre-une-formation-bioforce-en-e-learning-et-une-formation-en-presentiel/"
]

# Mots-clés de recherche pour trouver davantage de FAQs
SEARCH_KEYWORDS = [
    "formation", "e-learning", "comment", "quels", "quelle", 
    "pourquoi", "quand", "qui", "où", "combien", "frais", 
    "inscription", "diplôme", "certification", "financement",
    "stage", "emploi", "modalités", "valider", "candidature"
]

class MassFaqIndexer:
    """
    Classe pour extraire et indexer en masse les FAQ de Bioforce
    """
    def __init__(self):
        self.qdrant = QdrantConnector(collection_name=QDRANT_COLLECTION, is_full_site=False)
        self.total_faq = 0
        self.discovered_faq = 0
        self.successful_faq = 0
        self.failed_faq = 0
        self.session = None
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        self.faq_urls = set()
        
    async def run(self):
        """
        Exécute le processus complet d'extraction et d'indexation
        """
        start_time = datetime.now()
        logger.info(f"Début du processus d'indexation massive des FAQ: {start_time}")
        
        # Recréer la collection
        self._recreate_collection()
        
        # Créer une session HTTP réutilisable
        async with aiohttp.ClientSession() as self.session:
            # Découvrir autant de FAQ que possible
            await self._discover_faq_urls()
            
            # Indexer toutes les FAQ découvertes
            await self._index_all_faqs()
        
        # Afficher les statistiques
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        self._print_stats(duration)
        
        logger.info(f"Fin du processus d'indexation massive: {end_time}")
        logger.info(f"Durée totale: {duration:.2f} secondes")
        
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
    
    async def _discover_faq_urls(self):
        """
        Découvre les URLs des FAQ par différentes méthodes
        """
        logger.info("Début de la découverte des URLs de FAQ...")
        
        # Ajouter les URLs déjà connues
        self.faq_urls.update(KNOWN_FAQ_URLS)
        logger.info(f"Ajout de {len(KNOWN_FAQ_URLS)} URLs connues")
        
        # 1. Méthode: explorer les URL connues et extraire les liens connexes
        tasks = []
        for url in KNOWN_FAQ_URLS[:5]:  # Limiter pour éviter de surcharger
            tasks.append(self._extract_related_faqs(url))
        
        related_urls_lists = await asyncio.gather(*tasks)
        for urls in related_urls_lists:
            self.faq_urls.update(urls)
        
        logger.info(f"Après recherche de liens connexes: {len(self.faq_urls)} URLs")
        
        # 2. Méthode: utiliser la recherche du site pour trouver plus de FAQ
        search_tasks = []
        for keyword in SEARCH_KEYWORDS[:10]:  # Limiter pour éviter de surcharger
            search_tasks.append(self._search_for_faqs(keyword))
        
        search_results = await asyncio.gather(*search_tasks)
        for urls in search_results:
            self.faq_urls.update(urls)
        
        logger.info(f"Après recherche par mots-clés: {len(self.faq_urls)} URLs")
        
        # 3. Méthode: explorer la page d'accueil et principales sections
        main_pages = [
            "https://www.bioforce.org",
            "https://www.bioforce.org/formation/",
            "https://www.bioforce.org/contact/",
            "https://www.bioforce.org/a-propos/"
        ]
        
        main_tasks = []
        for url in main_pages:
            main_tasks.append(self._extract_faq_links_from_page(url))
        
        main_results = await asyncio.gather(*main_tasks)
        for urls in main_results:
            self.faq_urls.update(urls)
        
        self.discovered_faq = len(self.faq_urls)
        logger.info(f"Total des URLs de FAQ découvertes: {self.discovered_faq}")
    
    async def _extract_related_faqs(self, url: str) -> Set[str]:
        """
        Extrait les liens vers d'autres FAQ à partir d'une page FAQ
        """
        async with self.semaphore:
            try:
                related_urls = set()
                
                # Attendre un court délai pour éviter de surcharger le serveur
                await asyncio.sleep(0.2)
                
                async with self.session.get(url) as response:
                    if response.status != 200:
                        logger.warning(f"Erreur {response.status} lors de l'accès à {url}")
                        return related_urls
                    
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Extraire tous les liens
                    for a in soup.find_all('a', href=True):
                        href = a.get('href', '').strip()
                        if not href:
                            continue
                        
                        # Convertir en URL absolue
                        abs_url = urljoin(url, href)
                        
                        # Vérifier si c'est un lien de question
                        if re.match(QUESTION_URL_PATTERN, abs_url):
                            related_urls.add(abs_url)
                
                logger.info(f"Trouvé {len(related_urls)} FAQ(s) liées depuis {url}")
                return related_urls
                
            except Exception as e:
                logger.error(f"Erreur lors de l'extraction des FAQ liées depuis {url}: {e}")
                return set()
    
    async def _search_for_faqs(self, keyword: str) -> Set[str]:
        """
        Utilise la recherche du site pour trouver des FAQ
        """
        async with self.semaphore:
            try:
                search_urls = set()
                search_url = f"{BIOFORCE_BASE_URL}/?s={keyword}"
                
                # Attendre un court délai
                await asyncio.sleep(0.2)
                
                async with self.session.get(search_url) as response:
                    if response.status != 200:
                        logger.warning(f"Erreur {response.status} lors de la recherche avec '{keyword}'")
                        return search_urls
                    
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Extraire tous les liens des résultats de recherche
                    for a in soup.find_all('a', href=True):
                        href = a.get('href', '').strip()
                        if not href:
                            continue
                        
                        # Convertir en URL absolue
                        abs_url = urljoin(search_url, href)
                        
                        # Vérifier si c'est un lien de question
                        if re.match(QUESTION_URL_PATTERN, abs_url):
                            search_urls.add(abs_url)
                
                logger.info(f"Trouvé {len(search_urls)} FAQ(s) via recherche '{keyword}'")
                return search_urls
                
            except Exception as e:
                logger.error(f"Erreur lors de la recherche avec '{keyword}': {e}")
                return set()
    
    async def _extract_faq_links_from_page(self, url: str) -> Set[str]:
        """
        Extrait tous les liens vers des FAQ depuis une page quelconque
        """
        async with self.semaphore:
            try:
                faq_urls = set()
                
                # Attendre un court délai
                await asyncio.sleep(0.2)
                
                async with self.session.get(url) as response:
                    if response.status != 200:
                        logger.warning(f"Erreur {response.status} lors de l'accès à {url}")
                        return faq_urls
                    
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Extraire tous les liens
                    for a in soup.find_all('a', href=True):
                        href = a.get('href', '').strip()
                        if not href:
                            continue
                        
                        # Convertir en URL absolue
                        abs_url = urljoin(url, href)
                        
                        # Vérifier si c'est un lien de question
                        if re.match(QUESTION_URL_PATTERN, abs_url):
                            faq_urls.add(abs_url)
                
                logger.info(f"Trouvé {len(faq_urls)} FAQ(s) depuis {url}")
                return faq_urls
                
            except Exception as e:
                logger.error(f"Erreur lors de l'extraction depuis {url}: {e}")
                return set()
    
    async def _index_all_faqs(self):
        """
        Indexe toutes les FAQ découvertes
        """
        logger.info(f"Début de l'indexation de {len(self.faq_urls)} FAQ...")
        
        # Traiter toutes les URLs par lots
        batch_size = 10
        url_list = list(self.faq_urls)
        
        for i in range(0, len(url_list), batch_size):
            batch = url_list[i:i+batch_size]
            logger.info(f"Traitement du lot {i//batch_size + 1}/{(len(url_list)+batch_size-1)//batch_size} ({len(batch)} URLs)")
            
            # Traiter ce lot en parallèle
            tasks = [self._process_and_index_faq(url) for url in batch]
            await asyncio.gather(*tasks)
            
            # Attendre un court délai entre les lots
            await asyncio.sleep(0.5)
        
        logger.info(f"Indexation terminée: {self.successful_faq}/{self.total_faq} réussies")
    
    async def _process_and_index_faq(self, url: str):
        """
        Traite et indexe une FAQ
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
                
                # Attendre un court délai
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
                    
                    if not title or not content:
                        logger.warning(f"Extraction incomplète pour {url}")
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
        
        # Approche 2: Extraire depuis l'URL
        match = re.search(r'/question/([^/]+)/?$', url)
        if match:
            slug = match.group(1)
            title = slug.replace('-', ' ').capitalize()
            return title
        
        # Approche 3: Utiliser le texte du premier paragraphe
        paragraphs = soup.find_all('p')
        if paragraphs and paragraphs[0].get_text().strip():
            text = paragraphs[0].get_text().strip()
            # Limiter à la première phrase si le paragraphe est long
            if len(text) > 100 and '.' in text[:100]:
                return text.split('.')[0] + '.'
            return text[:100] + ('...' if len(text) > 100 else '')
        
        return "Question FAQ Bioforce"
    
    def _extract_content(self, soup: BeautifulSoup, url: str) -> str:
        """
        Extrait le contenu (réponse) d'une page FAQ
        """
        # Approche 1: Zone de contenu principale
        content_areas = soup.select('div.entry-content, article, div.post-content, main')
        if content_areas:
            # Supprimer les éléments non pertinents
            for element in content_areas[0].select('header, footer, nav, .navigation, .sidebar'):
                if element:
                    element.decompose()
            
            # Extraire le texte
            content = content_areas[0].get_text().strip()
            if content:
                # Nettoyer le contenu (supprimer les espaces multiples, etc.)
                content = re.sub(r'\s+', ' ', content).strip()
                return content
        
        # Approche 2: Tous les paragraphes
        paragraphs = soup.find_all(['p', 'div.paragraph'])
        if paragraphs:
            content = ' '.join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])
            if content:
                return content
        
        # En dernier recours, extraire du texte depuis l'URL
        match = re.search(r'/question/([^/]+)/?$', url)
        if match:
            slug = match.group(1)
            default_content = (
                f"Cette question concerne {slug.replace('-', ' ')}. "
                "Veuillez consulter la page originale pour plus d'informations détaillées."
            )
            return default_content
        
        return "Information non disponible. Veuillez consulter le site Bioforce pour plus de détails."
    
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
        logger.info("=== Statistiques d'indexation massive des FAQ ===")
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
    logger.info(f"Début du processus d'indexation massive des FAQ: {start_time}")
    
    indexer = MassFaqIndexer()
    await indexer.run()
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    logger.info(f"Fin du processus: {end_time}")
    logger.info(f"Durée totale: {duration:.2f} secondes")

if __name__ == "__main__":
    asyncio.run(main())
