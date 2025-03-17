"""
Module pour la priorisation des URLs à scraper
"""
import logging
import re
from typing import List

from bioforce_scraper.config import LOG_FILE
from bioforce_scraper.utils.logger import setup_logger

logger = setup_logger(__name__, LOG_FILE)

def prioritize_url(url: str, priority_patterns: List[str]) -> int:
    """
    Attribue une priorité à une URL en fonction de patterns prédéfinis
    
    Args:
        url: URL à évaluer
        priority_patterns: Liste de patterns à rechercher dans l'URL
        
    Returns:
        Score de priorité (plus élevé = plus prioritaire)
    """
    url_lower = url.lower()
    priority = 1  # Priorité de base
    
    # Augmenter la priorité en fonction des patterns trouvés
    for i, pattern in enumerate(priority_patterns):
        if pattern.lower() in url_lower:
            # Donner plus de poids aux patterns en début de liste
            priority += (len(priority_patterns) - i)
    
    # Ajustements spécifiques
    
    # Très haute priorité pour les pages de formation et d'admission
    if re.search(r'(formation|learn|cours|programme).*(\d{4}|\d{2}-\d{2})', url_lower):
        priority += 5  # Programme spécifique à une année
    
    if '/admission/' in url_lower or '/candidature/' in url_lower:
        priority += 4
    
    # Priorité aux pages de niveau 1 et 2 (peu de slashes)
    depth = url.count('/')
    if url.endswith('/'):
        depth -= 1
    
    # URL de profondeur 2-3 sont généralement les plus informatives
    if depth <= 4:
        priority += 3
    elif depth <= 6:
        priority += 1
    else:
        priority -= 1  # Pénaliser les URLs trop profondes
    
    # Priorité aux PDF
    if url.lower().endswith('.pdf'):
        priority += 2
    
    # Priorité aux pages en français (Bioforce étant une organisation française)
    if '/fr/' in url_lower:
        priority += 1
    
    # Pénaliser certains types de pages moins pertinentes
    if any(x in url_lower for x in ['/tag/', '/author/', '/comment/', '/feed/']):
        priority -= 3
    
    # Limiter la priorité à un minimum de 0
    return max(0, priority)
