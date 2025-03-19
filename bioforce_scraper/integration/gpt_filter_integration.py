"""
Module d'intégration du filtrage GPT pour le scraper principal
"""
from typing import Dict, Any, List, Optional

from bioforce_scraper.config import LOG_FILE
from bioforce_scraper.utils.logger import setup_logger
from bioforce_scraper.utils.content_filter import ContentFilterGPT

# Configuration du logger
logger = setup_logger(__name__, LOG_FILE)

class GPTFilterIntegration:
    """
    Intégration du filtrage GPT dans le processus de scraping
    """
    
    def __init__(self):
        """
        Initialise l'intégration du filtrage GPT
        """
        self.content_filter = ContentFilterGPT()
        self.filtered_html_count = 0
        self.filtered_pdf_count = 0
        self.enhanced_html_count = 0
        self.enhanced_pdf_count = 0
    
    async def process_html_content(self, content: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Traite le contenu HTML avec le filtre GPT
        
        Args:
            content: Contenu HTML extrait
            
        Returns:
            Contenu filtré ou None si le contenu est filtré
        """
        try:
            logger.info(f"Filtrage GPT du contenu HTML de: {content.get('url', 'URL inconnue')}")
            
            # Filtrer et améliorer le contenu
            enhanced_content, is_useful = await self.content_filter.filter_page_content(content)
            
            if not is_useful:
                self.filtered_html_count += 1
                logger.info(f"Contenu HTML filtré: {content.get('url', 'URL inconnue')}")
                return None
            
            if enhanced_content.get("gpt_enhanced", False):
                self.enhanced_html_count += 1
                logger.info(f"Contenu HTML amélioré: {content.get('url', 'URL inconnue')}")
            
            return enhanced_content
            
        except Exception as e:
            logger.error(f"Erreur lors du filtrage GPT du contenu HTML: {e}")
            return content  # Retourner le contenu original en cas d'erreur
    
    async def process_pdf_content(self, content: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Traite le contenu PDF avec le filtre GPT
        
        Args:
            content: Contenu PDF extrait
            
        Returns:
            Contenu filtré ou None si le contenu est filtré
        """
        try:
            logger.info(f"Filtrage GPT du contenu PDF de: {content.get('url', 'URL inconnue')}")
            
            # Filtrer et améliorer le contenu
            enhanced_content, is_useful = await self.content_filter.filter_pdf_content(content)
            
            if not is_useful:
                self.filtered_pdf_count += 1
                logger.info(f"Contenu PDF filtré: {content.get('url', 'URL inconnue')}")
                return None
            
            if enhanced_content.get("gpt_enhanced", False):
                self.enhanced_pdf_count += 1
                logger.info(f"Contenu PDF amélioré: {content.get('url', 'URL inconnue')}")
            
            return enhanced_content
            
        except Exception as e:
            logger.error(f"Erreur lors du filtrage GPT du contenu PDF: {e}")
            return content  # Retourner le contenu original en cas d'erreur
    
    async def process_faq_items(self, faq_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Traite les éléments FAQ avec le filtre GPT
        
        Args:
            faq_items: Liste des éléments FAQ
            
        Returns:
            Liste des éléments FAQ filtrés
        """
        try:
            if not faq_items:
                return []
                
            logger.info(f"Filtrage GPT de {len(faq_items)} éléments FAQ")
            
            # Filtrer les éléments FAQ
            kept_items, filtered_items = await self.content_filter.filter_faq_content(faq_items)
            
            logger.info(f"Résultat du filtrage FAQ: {len(kept_items)} conservés, {len(filtered_items)} filtrés")
            
            return kept_items
            
        except Exception as e:
            logger.error(f"Erreur lors du filtrage GPT des éléments FAQ: {e}")
            return faq_items  # Retourner les éléments originaux en cas d'erreur
    
    def get_statistics(self) -> Dict[str, int]:
        """
        Retourne les statistiques de filtrage
        
        Returns:
            Dictionnaire des statistiques
        """
        return {
            "filtered_html_count": self.filtered_html_count,
            "filtered_pdf_count": self.filtered_pdf_count,
            "enhanced_html_count": self.enhanced_html_count,
            "enhanced_pdf_count": self.enhanced_pdf_count,
            "total_filtered": self.filtered_html_count + self.filtered_pdf_count,
            "total_enhanced": self.enhanced_html_count + self.enhanced_pdf_count
        }
