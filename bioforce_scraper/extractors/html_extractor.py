"""
Module pour l'extraction de contenu à partir des pages HTML
"""
import asyncio
import re
from typing import Dict, List, Any

# Import absolus pour éviter les problèmes lorsque le module est importé depuis l'API
import sys
import pathlib
# Ajouter le répertoire parent au path pour pouvoir importer les modules
sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))

from bs4 import BeautifulSoup
from playwright.async_api import Page, TimeoutError
from bioforce_scraper.config import LOG_FILE, MAX_RETRIES, RETRY_DELAY, MAX_TIMEOUT
from bioforce_scraper.utils.logger import setup_logger

logger = setup_logger(__name__, LOG_FILE)

# Éléments à exclure lors de l'extraction du contenu
EXCLUDE_SELECTORS = [
    'header', 'footer', 'nav', '.menu', '.sidebar', '.widget', 
    '.cookie-notice', '.social-links', '#comments', '.comments',
    '.wp-block-buttons', '.wp-block-social-links', '.wpcf7',
    'style', 'script', 'noscript', '[class*="cookie"]', 
    '.menu-item', '.elementor-widget-container'
]

# Éléments qui contiennent potentiellement du contenu important
CONTENT_SELECTORS = [
    'article', 'main', '.content', '.entry-content', '.post-content',
    '.page-content', '#content', '.entry', '.post', '.page',
    '.site-content', '.bioforce-content', '.formation-details',
    '.admission-process', '.programme-details', '.learn-section',
    '.build-section'
]

async def extract_html_content(page: Page, url: str) -> Dict[str, Any]:
    """
    Extrait le contenu d'une page HTML utilisant Playwright avec système de retry
    
    Args:
        page: L'objet page Playwright
        url: L'URL de la page à extraire
        
    Returns:
        Un dictionnaire contenant le contenu et les métadonnées extraits
    """
    for attempt in range(MAX_RETRIES):
        try:
            # Naviguer vers l'URL avec timeout
            await page.goto(url, timeout=MAX_TIMEOUT * 1000, wait_until='networkidle')
            
            # Attendre que le contenu soit chargé
            await page.wait_for_load_state('domcontentloaded')
            
            # Récupérer le contenu HTML complet
            html_content = await page.content()
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extraire le titre
            title = await page.title()
            
            # Extraire le contenu principal
            main_content = await extract_main_content(page, soup)
            
            # Extraire les métadonnées
            metadata = extract_metadata(soup)
            
            # Extraire les liens
            links = await extract_links(page, url)
            
            # Assembler le résultat
            result = {
                'title': title,
                'text': main_content,
                'metadata': metadata,
                'links': links,
                'html': html_content,
                'url': url
            }
            
            return result
            
        except TimeoutError:
            logger.warning(f"Timeout lors du chargement de {url}, tentative {attempt+1}/{MAX_RETRIES}")
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY)
            else:
                logger.error(f"Échec après {MAX_RETRIES} tentatives pour {url}")
                raise
                
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction de contenu pour {url}: {str(e)}")
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY)
            else:
                logger.error(f"Échec après {MAX_RETRIES} tentatives pour {url}")
                raise

async def extract_main_content(page: Page, soup: BeautifulSoup) -> str:
    """
    Extrait le contenu principal de la page
    
    Args:
        page: L'objet page Playwright
        soup: L'objet BeautifulSoup
        
    Returns:
        Le texte principal
    """
    # Essayer d'extraire le contenu via JavaScript
    content = await page.evaluate("""() => {
        // Essayer de trouver le contenu principal
        const contentSelectors = [
            'article', 'main', '.content', '.entry-content', '.post-content',
            '.page-content', '#content', '.entry', '.post', '.page',
            '.site-content', '.bioforce-content', '.formation-details'
        ];
        
        for (const selector of contentSelectors) {
            const element = document.querySelector(selector);
            if (element) {
                return element.innerText;
            }
        }
        
        // Fallback: utiliser le body si aucun contenu principal n'est trouvé
        return document.body.innerText;
    }""")
    
    # Si le contenu est vide ou trop court, essayer avec BeautifulSoup
    if not content or len(content) < 100:
        # Supprimer les éléments non pertinents
        for selector in EXCLUDE_SELECTORS:
            for element in soup.select(selector):
                element.decompose()
                
        # Chercher les sections de contenu principales
        main_content = ""
        for selector in CONTENT_SELECTORS:
            elements = soup.select(selector)
            if elements:
                for element in elements:
                    main_content += element.get_text(separator=" ", strip=True) + "\n\n"
                
        # Si aucun contenu principal n'a été trouvé, utiliser tout le body
        if not main_content:
            main_content = soup.body.get_text(separator=" ", strip=True)
            
        content = main_content
    
    # Nettoyer le texte
    return clean_text(content)

def clean_text(text: str) -> str:
    """
    Nettoie le texte extrait
    
    Args:
        text: Le texte à nettoyer
        
    Returns:
        Le texte nettoyé
    """
    if not text:
        return ""
        
    # Supprimer les espaces multiples
    text = re.sub(r'\s+', ' ', text)
    
    # Supprimer les lignes vides
    text = re.sub(r'\n\s*\n', '\n', text)
    
    # Supprimer les caractères spéciaux et les séquences non imprimables
    text = re.sub(r'[\x00-\x1F\x7F]', '', text)
    
    return text.strip()

def extract_metadata(soup: BeautifulSoup) -> Dict[str, str]:
    """
    Extrait les métadonnées depuis les balises meta
    
    Args:
        soup: L'objet BeautifulSoup
        
    Returns:
        Un dictionnaire des métadonnées
    """
    metadata = {}
    
    # Extraire les balises meta
    meta_tags = soup.find_all('meta')
    for tag in meta_tags:
        if tag.get('name') and tag.get('content'):
            metadata[tag['name']] = tag['content']
        elif tag.get('property') and tag.get('content'):
            metadata[tag['property']] = tag['content']
            
    # Extraire d'autres informations utiles
    if soup.find('time'):
        time_tag = soup.find('time')
        if time_tag.get('datetime'):
            metadata['published_date'] = time_tag['datetime']
            
    return metadata

async def extract_links(page: Page, base_url: str) -> List[str]:
    """
    Extrait tous les liens de la page
    
    Args:
        page: L'objet page Playwright
        base_url: L'URL de base pour résoudre les liens relatifs
        
    Returns:
        Liste des URLs extraites
    """
    # Extraire tous les liens via JavaScript
    links = await page.evaluate("""(baseUrl) => {
        const links = Array.from(document.querySelectorAll('a[href]'))
            .map(a => {
                try {
                    return new URL(a.href, baseUrl).href;
                } catch (e) {
                    return null;
                }
            })
            .filter(href => href !== null);
        return [...new Set(links)]; // Éliminer les doublons
    }""", base_url)
    
    return links
