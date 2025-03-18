"""
Module pour analyser le sitemap XML de Bioforce et extraire les URLs pertinentes
"""
import asyncio
import re
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urlparse

import aiohttp
from bs4 import BeautifulSoup

import sys
import pathlib
# Ajouter le répertoire parent au path pour pouvoir importer les modules
sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))

from bioforce_scraper.config import BASE_URL, LOG_FILE
from bioforce_scraper.utils.logger import setup_logger

# Configuration du logger
logger = setup_logger(__name__, LOG_FILE)

class SitemapParser:
    """
    Classe pour analyser les sitemaps XML et extraire les URLs pertinentes
    """
    
    def __init__(self, sitemap_url: str = None):
        """
        Initialise le parser de sitemap
        
        Args:
            sitemap_url: URL du sitemap principal, par défaut: BASE_URL + '/sitemap.xml'
        """
        self.sitemap_url = sitemap_url or f"{BASE_URL}/sitemap.xml"
        self.urls = set()
        self.sitemaps = set()
        self.urls_with_priority = []  # Liste de tuples (url, priorité, date de modification)
        self.faq_urls = {}  # Dictionnaire {url: dernière_modification} pour les FAQs
        
        # Patterns pour filtrer les URLs pertinentes
        self.high_priority_patterns = [
            r'/formation/',
            r'/candidature/',
            r'/financement/',
            r'/faq/',
            r'/question/',
            r'/learn/',
            r'/about/'
        ]
        
        # Patterns pour identifier les FAQs
        self.faq_patterns = [
            r'/question/',
            r'/?faq=',
            r'/faq-',
            r'/faq/'
        ]
        
        # Patterns pour exclure des URLs non pertinentes
        self.exclude_patterns = [
            r'/wp-',
            r'/tag/',
            r'/author/',
            r'/comment-page-',
            r'/feed/',
            r'\.js$',
            r'\.css$',
            r'\.jpg$',
            r'\.jpeg$',
            r'\.png$',
            r'\.gif$'
        ]
    
    async def fetch_sitemap(self, url: str) -> Optional[str]:
        """
        Récupère le contenu d'un sitemap XML
        
        Args:
            url: URL du sitemap à récupérer
            
        Returns:
            Contenu du sitemap ou None en cas d'erreur
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as response:
                    if response.status == 200:
                        content = await response.text()
                        logger.info(f"Sitemap récupéré avec succès: {url}")
                        return content
                    else:
                        logger.error(f"Erreur lors de la récupération du sitemap {url}: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Exception lors de la récupération du sitemap {url}: {e}")
            return None
    
    def is_relevant_url(self, url: str) -> Tuple[bool, float]:
        """
        Détermine si une URL est pertinente pour le scraping et calcule sa priorité
        
        Args:
            url: URL à vérifier
            
        Returns:
            Tuple (est_pertinente, priorité)
        """
        # Vérifier si l'URL correspond aux patterns d'exclusion
        for pattern in self.exclude_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return False, 0.0
        
        # Calculer la priorité en fonction des patterns de haute priorité
        priority = 0.5  # Priorité par défaut
        
        for pattern in self.high_priority_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                priority = 0.9
                break
        
        # Donner une priorité plus élevée aux URLs courtes (souvent plus importantes)
        path_length = len(urlparse(url).path.split('/'))
        if path_length <= 3:
            priority += 0.1
        
        return True, min(priority, 1.0)  # Plafonner à 1.0
    
    async def parse_sitemap(self, content: str, is_index: bool = False) -> None:
        """
        Analyse le contenu d'un sitemap XML et extrait les URLs
        
        Args:
            content: Contenu du sitemap
            is_index: Si True, le sitemap est un index de sitemaps
        """
        soup = BeautifulSoup(content, 'xml')
        
        if is_index or soup.find('sitemapindex'):
            # C'est un index de sitemaps
            sitemap_tags = soup.find_all('sitemap')
            for sitemap in sitemap_tags:
                loc = sitemap.find('loc')
                if loc and loc.string:
                    self.sitemaps.add(loc.string)
            
            logger.info(f"Index de sitemap analysé: {len(self.sitemaps)} sitemaps trouvés")
        else:
            # C'est un sitemap régulier
            url_tags = soup.find_all('url')
            new_urls = 0
            
            for url_tag in url_tags:
                loc = url_tag.find('loc')
                if not loc or not loc.string:
                    continue
                
                url = loc.string
                
                # Vérifier la pertinence de l'URL
                is_relevant, priority = self.is_relevant_url(url)
                if not is_relevant:
                    continue
                
                # Extraire la date de dernière modification si présente
                lastmod = url_tag.find('lastmod')
                lastmod_date = lastmod.string if lastmod else None
                
                # Extraire la priorité du sitemap si présente
                priority_tag = url_tag.find('priority')
                if priority_tag and priority_tag.string:
                    try:
                        sitemap_priority = float(priority_tag.string)
                        # Combiner notre priorité calculée avec celle du sitemap
                        priority = (priority + sitemap_priority) / 2
                    except (ValueError, TypeError):
                        pass
                
                # Ajouter l'URL à notre ensemble
                if url not in self.urls:
                    self.urls.add(url)
                    self.urls_with_priority.append((url, priority, lastmod_date))
                    new_urls += 1
                    
                # Vérifier si l'URL est une FAQ
                for pattern in self.faq_patterns:
                    if re.search(pattern, url, re.IGNORECASE):
                        self.faq_urls[url] = lastmod_date
                        break
            
            logger.info(f"Sitemap analysé: {new_urls} nouvelles URLs pertinentes trouvées")
    
    async def parse_faq_sitemap(self, sitemap_url: str) -> Dict[str, Any]:
        """
        Parse spécifiquement le sitemap des FAQs (questions) et retourne leurs URLs avec dates de modification
        
        Args:
            sitemap_url: URL du sitemap des FAQs (ex: question-sitemap.xml)
            
        Returns:
            Dictionnaire {url: date_modification} pour les FAQs
        """
        logger.info(f"Parsing du sitemap FAQ: {sitemap_url}")
        content = await self.fetch_sitemap(sitemap_url)
        
        if not content:
            logger.error(f"Impossible de récupérer le sitemap FAQ: {sitemap_url}")
            return {}
        
        soup = BeautifulSoup(content, 'xml')
        urls_with_dates = {}
        
        # Extraire les URLs et les dates de dernière modification
        for url_tag in soup.find_all('url'):
            loc = url_tag.find('loc')
            lastmod = url_tag.find('lastmod')
            
            if loc:
                url = loc.text.strip()
                lastmod_date = None
                
                if lastmod:
                    try:
                        # Format YYYY-MM-DD ou YYYY-MM-DDThh:mm:ss+00:00
                        lastmod_text = lastmod.text.strip()
                        if 'T' in lastmod_text:
                            lastmod_date = lastmod_text.split('+')[0]
                        else:
                            lastmod_date = lastmod_text
                    except Exception as e:
                        logger.warning(f"Erreur de parsing de date pour {url}: {e}")
                
                # Vérifier si c'est une FAQ
                if any(re.search(pattern, url, re.IGNORECASE) for pattern in self.faq_patterns):
                    urls_with_dates[url] = lastmod_date
                    logger.debug(f"URL FAQ trouvée: {url}, dernière modification: {lastmod_date}")
        
        logger.info(f"{len(urls_with_dates)} URLs FAQ trouvées dans le sitemap")
        return urls_with_dates
    
    async def run(self) -> List[Dict[str, Any]]:
        """
        Exécute l'analyse du sitemap principal et de tous les sous-sitemaps
        
        Returns:
            Liste d'URLs avec leurs priorités, au format compatible avec le scraper
        """
        logger.info(f"Début de l'analyse du sitemap: {self.sitemap_url}")
        
        # Récupérer le sitemap principal
        content = await self.fetch_sitemap(self.sitemap_url)
        if not content:
            logger.error("Impossible de récupérer le sitemap principal")
            return []
        
        # Analyser le sitemap principal
        await self.parse_sitemap(content, is_index=True)
        
        # Traiter tous les sous-sitemaps
        for sitemap_url in self.sitemaps:
            content = await self.fetch_sitemap(sitemap_url)
            if content:
                await self.parse_sitemap(content)
        
        # Trier les URLs par priorité (décroissante)
        self.urls_with_priority.sort(key=lambda x: x[1], reverse=True)
        
        # Convertir au format attendu par le scraper
        result = [
            {"url": url, "priority": priority * 10, "depth": 0, "lastmod": lastmod}
            for url, priority, lastmod in self.urls_with_priority
        ]
        
        logger.info(f"Analyse du sitemap terminée: {len(result)} URLs pertinentes trouvées")
        return result

# Pour tester le module en standalone
async def main():
    parser = SitemapParser()
    urls = await parser.run()
    
    # Afficher les 10 premières URLs avec leur priorité
    for i, item in enumerate(urls[:10]):
        print(f"{i+1}. {item['url']} (priorité: {item['priority']}, modifié: {item.get('lastmod', 'N/A')})")
    
    print(f"Total: {len(urls)} URLs trouvées")

if __name__ == "__main__":
    asyncio.run(main())
