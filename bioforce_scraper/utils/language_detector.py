"""
Module pour la détection de la langue du contenu
"""
import logging
from typing import Optional

from langdetect import detect, DetectorFactory, LangDetectException
from bioforce_scraper.config import LOG_FILE, SUPPORTED_LANGUAGES
from bioforce_scraper.utils.logger import setup_logger

logger = setup_logger(__name__, LOG_FILE)

# Fixer la graine pour avoir des résultats déterministes
DetectorFactory.seed = 0

def detect_language(text: str) -> str:
    """
    Détecte la langue d'un texte
    
    Args:
        text: Texte à analyser
        
    Returns:
        Code ISO de la langue (fr, en, etc.) ou 'unknown'
    """
    if not text or len(text.strip()) < 50:
        return "unknown"
    
    try:
        # Prendre un échantillon représentatif pour la détection
        sample = text[:1000]
        lang = detect(sample)
        
        # Vérifier si la langue est supportée
        if lang in SUPPORTED_LANGUAGES:
            return lang
        else:
            logger.info(f"Langue détectée non supportée: {lang}")
            return "unknown"
    
    except LangDetectException as e:
        logger.warning(f"Erreur de détection de langue: {str(e)}")
        return "unknown"
    
    except Exception as e:
        logger.error(f"Erreur lors de la détection de langue: {str(e)}")
        return "unknown"
