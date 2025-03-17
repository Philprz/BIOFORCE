"""
Module pour l'extraction de contenu à partir des pages HTML
"""
import logging
import re
from typing import Dict, List, Any

from bs4 import BeautifulSoup
from config import LOG_FILE
from utils.logger import setup_logger

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

async def extract_page_content(page) -> Dict[str, Any]:
    """
    Extrait le contenu d'une page HTML utilisant Playwright
    
    Args:
        page: L'objet page Playwright
        
    Returns:
        Un dictionnaire contenant le contenu extrait
    """
    try:
        # Récupérer l'URL, le titre et le contenu HTML complet
        url = page.url
        title = await page.title()
        html_content = await page.content()
        
        # Utiliser BeautifulSoup pour analyser le HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extraire les métadonnées
        metadata = extract_metadata(soup)
        
        # Supprimer les éléments non pertinents
        for selector in EXCLUDE_SELECTORS:
            for element in soup.select(selector):
                element.decompose()
        
        # Trouver les principaux conteneurs de contenu
        content_element = None
        for selector in CONTENT_SELECTORS:
            elements = soup.select(selector)
            if elements:
                # Prendre le plus grand conteneur de contenu
                content_element = max(elements, key=lambda e: len(str(e)))
                break
        
        # Si aucun conteneur spécifique n'est trouvé, utiliser le corps
        if not content_element:
            content_element = soup.body
        
        # Extraire les en-têtes
        headings = extract_headings(content_element if content_element else soup)
        
        # Extraire le texte principal
        main_text = extract_main_text(content_element if content_element else soup)
        
        # Extraire les listes
        list_items = extract_lists(content_element if content_element else soup)
        
        # Extraire les informations de contact
        contact_info = extract_contact_info(soup)
        
        # Combiner tous les textes
        combined_text = main_text
        if list_items:
            combined_text += "\n\n" + list_items
        
        # Nettoyer le texte
        clean_text = clean_text_content(combined_text)
        
        return {
            'title': title,
            'content': clean_text,
            'headings': headings,
            'metadata': {
                **metadata,
                'contact_info': contact_info,
                'url': url
            }
        }
    
    except Exception as e:
        logger.error(f"Erreur lors de l'extraction du contenu: {str(e)}")
        return {'title': '', 'content': '', 'headings': [], 'metadata': {}}

def extract_metadata(soup) -> Dict[str, str]:
    """Extrait les métadonnées depuis les balises meta"""
    metadata = {}
    
    # Extraire les balises meta standard
    for meta in soup.find_all('meta'):
        name = meta.get('name') or meta.get('property')
        content = meta.get('content')
        if name and content:
            metadata[name] = content
    
    # Extraire la date de publication/mise à jour
    published = soup.select_one('time.published, .published-date, [class*="date"], [class*="time"]')
    if published:
        metadata['published_date'] = published.get_text().strip()
    
    # Extraire l'auteur
    author = soup.select_one('[rel="author"], .author, .byline')
    if author:
        metadata['author'] = author.get_text().strip()
    
    return metadata

def extract_headings(element) -> List[Dict[str, str]]:
    """Extrait les en-têtes (h1-h4) et leur texte"""
    headings = []
    
    for tag in ['h1', 'h2', 'h3', 'h4']:
        for heading in element.find_all(tag):
            heading_text = heading.get_text().strip()
            if heading_text:
                headings.append({
                    'level': tag,
                    'text': heading_text
                })
    
    return headings

def extract_main_text(element) -> str:
    """Extrait le texte principal du contenu"""
    paragraphs = []
    
    # Sélectionner tous les paragraphes et divs avec du texte
    for p in element.find_all(['p', 'div']):
        # Ignorer les éléments vides ou qui contiennent uniquement des éléments non pertinents
        if p.name == 'div' and (p.find(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']) or 
                               not p.get_text(strip=True)):
            continue
        
        text = p.get_text().strip()
        if text:
            paragraphs.append(text)
    
    # Traiter les en-têtes pour les inclure dans le texte
    for h in element.find_all(['h1', 'h2', 'h3', 'h4']):
        text = h.get_text().strip()
        if text:
            paragraphs.append(f"{h.name.upper()}: {text}")
    
    return "\n\n".join(paragraphs)

def extract_lists(element) -> str:
    """Extrait les éléments de liste (ul/ol)"""
    list_texts = []
    
    for list_elem in element.find_all(['ul', 'ol']):
        list_type = "• " if list_elem.name == 'ul' else "1. "
        items = []
        
        for i, item in enumerate(list_elem.find_all('li')):
            text = item.get_text().strip()
            if text:
                if list_elem.name == 'ol':
                    items.append(f"{i+1}. {text}")
                else:
                    items.append(f"• {text}")
        
        if items:
            list_texts.append("\n".join(items))
    
    return "\n\n".join(list_texts)

def extract_contact_info(soup) -> Dict[str, str]:
    """Extrait les informations de contact"""
    contact_info = {}
    
    # Rechercher les e-mails
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = re.findall(email_pattern, str(soup))
    if emails:
        contact_info['emails'] = list(set(emails))
    
    # Rechercher les numéros de téléphone
    phone_pattern = r'(?:\+\d{1,3}\s?)?(?:\(\d{1,4}\)\s?)?(?:\d{1,4}[\s.-]?){2,}'
    phones = re.findall(phone_pattern, str(soup))
    if phones:
        # Nettoyer les résultats
        cleaned_phones = [re.sub(r'\s+', ' ', phone).strip() for phone in phones]
        contact_info['phones'] = list(set(cleaned_phones))
    
    # Rechercher les adresses
    address_elems = soup.select('.address, [class*="adresse"], [itemprop="address"]')
    if address_elems:
        addresses = [elem.get_text().strip() for elem in address_elems]
        contact_info['addresses'] = list(set(addresses))
    
    return contact_info

def clean_text_content(text: str) -> str:
    """Nettoie le texte extrait"""
    # Supprimer les espaces multiples
    text = re.sub(r'\s+', ' ', text)
    
    # Supprimer les lignes vides
    text = re.sub(r'\n\s*\n', '\n\n', text)
    
    # Supprimer les espaces en début et fin de texte
    text = text.strip()
    
    # Ajouter des sauts de ligne après les points (pour améliorer la lisibilité)
    text = re.sub(r'\.(?=\s[A-Z])', '.\n', text)
    
    return text
