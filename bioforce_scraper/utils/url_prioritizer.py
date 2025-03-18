"""
Module pour la priorisation des URLs à scraper
"""
import logging
from typing import List

from bioforce_scraper.config import LOG_FILE, PRIORITY_PATTERNS
from bioforce_scraper.utils.logger import setup_logger

logger = setup_logger(__name__, LOG_FILE)

def prioritize_url(url: str, priority_patterns: List[str] = None) -> bool:
    """
    Détermine si une URL doit être priorisée en fonction des mots-clés définis dans PRIORITY_PATTERNS.

    Args:
        url: L'URL à vérifier
        priority_patterns: Liste des motifs à rechercher; si None, utilise PRIORITY_PATTERNS depuis la config.

    Returns:
        True si l'URL contient l'un des motifs de priorité, sinon False.
    """
    if priority_patterns is None:
        priority_patterns = PRIORITY_PATTERNS
    
    url_lower = url.lower()
    for pattern in priority_patterns:
        if pattern.lower() in url_lower:
            return True
    return False

"""
Exemple d'utilisation:

    >>> prioritize_url("https://www.bioforce.org/learn/")
    True
"""
