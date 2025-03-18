"""
Module pour filtrer les URLs selon différents critères
"""
import logging
import re
from typing import List, Optional
from urllib.parse import urlparse

# Import absolus pour éviter les problèmes lorsque le module est importé depuis l'API
import sys
import pathlib
# Ajouter le répertoire parent au path pour pouvoir importer les modules
sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))

from bioforce_scraper.config import BASE_URL, EXCLUDE_PATTERNS, LOG_FILE
from bioforce_scraper.utils.logger import setup_logger

# Configuration du logger
logger = setup_logger(__name__, LOG_FILE)

def is_valid_url(url: str, base_url: str = BASE_URL, exclude_patterns: List[str] = None) -> bool:
    """
    Vérifie si une URL est valide selon plusieurs critères:
    - Elle appartient au même domaine que base_url
    - Elle ne correspond pas aux patterns d'exclusion
    - Elle a une extension valide pour le scraping
    
    Args:
        url: L'URL à vérifier
        base_url: L'URL de base pour vérifier le domaine
        exclude_patterns: Liste de patterns regex à exclure (si None, utilise EXCLUDE_PATTERNS)
        
    Returns:
        True si l'URL est valide, False sinon
    """
    if exclude_patterns is None:
        exclude_patterns = EXCLUDE_PATTERNS
        
    # Vérifier si l'URL est vide ou None
    if not url:
        return False
        
    # Nettoyer l'URL (enlever les espaces, etc.)
    url = url.strip()
    
    try:
        # Vérifier si l'URL est bien formée
        result = urlparse(url)
        if not result.scheme or not result.netloc:
            logger.debug(f"URL invalide (format): {url}")
            return False
            
        # Vérifier si l'URL appartient au même domaine
        base_domain = urlparse(base_url).netloc
        if result.netloc != base_domain:
            logger.debug(f"URL invalide (domaine): {url}, attendu: {base_domain}")
            return False
            
        # Vérifier les patterns d'exclusion
        for pattern in exclude_patterns:
            if pattern.lower() in url.lower():
                logger.debug(f"URL exclue (pattern): {url}, pattern: {pattern}")
                return False
                
        # Vérifier si l'URL pointe vers un fichier à ignorer
        extensions_to_ignore = ['.jpg', '.jpeg', '.png', '.gif', '.css', '.js', '.svg', '.woff', '.woff2', '.ttf', '.eot']
        for ext in extensions_to_ignore:
            if url.lower().endswith(ext):
                logger.debug(f"URL exclue (extension): {url}")
                return False
                
        return True
        
    except Exception as e:
        logger.error(f"Erreur lors de la vérification de l'URL {url}: {str(e)}")
        return False

# Fonction alias pour la compatibilité avec main.py
def filter_url(url: str, base_url: str = BASE_URL, exclude_patterns: List[str] = None) -> bool:
    """
    Alias de is_valid_url pour la compatibilité avec main.py.
    Vérifie si une URL doit être incluse dans le processus de scraping.
    
    Args:
        url: L'URL à vérifier
        base_url: L'URL de base pour vérifier le domaine
        exclude_patterns: Liste de patterns regex à exclure
        
    Returns:
        True si l'URL doit être incluse, False sinon
    """
    return is_valid_url(url, base_url, exclude_patterns)
