"""
Module d'intégration pour le filtrage de contenu avec GPT
"""
from typing import Dict, Any, List, Optional

from bioforce_scraper.utils.logger import setup_logger
from bioforce_scraper.config import LOG_FILE

# Configuration du logger
logger = setup_logger(__name__, LOG_FILE)

class GPTFilterIntegration:
    """
    Classe pour filtrer et améliorer le contenu en utilisant GPT
    """
    def __init__(self):
        """Initialise le filtre GPT"""
        logger.info("Initialisation du filtre GPT")
    
    async def process_html_content(self, content_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Traite le contenu HTML pour l'améliorer et le filtrer
        
        Args:
            content_data: Dictionnaire contenant les données du contenu, incluant 
                          typiquement 'title', 'content', 'url', etc.
            
        Returns:
            Le dictionnaire de contenu filtré et amélioré ou None si le contenu
            n'est pas pertinent
        """
        try:
            # Vérifier que le contenu est présent
            if not content_data or 'content' not in content_data or not content_data['content']:
                logger.warning(f"Contenu manquant ou vide pour {content_data.get('url', 'URL inconnue')}")
                return None
            
            # On accepte tous les contenus pour l'indexation pour ne pas filtrer les contenus en anglais
            # On vérifiera la pertinence lors des recherches
            url = content_data.get('url', 'URL inconnue')
            title = content_data.get('title', 'Sans titre')
            lang = content_data.get('language', 'inconnu')
            
            # Détecter si c'est une FAQ ou un contenu prioritaire
            is_faq = content_data.get('is_faq', False) or 'faq' in url.lower() or 'question' in url.lower()
            is_course = 'formation' in url.lower() or 'course' in url.lower() or 'training' in url.lower()
            is_important = is_faq or is_course
            
            # Définir un score de pertinence par défaut
            # Les FAQ et formations ont un score plus élevé par défaut
            default_score = 0.9 if is_important else 0.7
            
            # Utiliser le score existant ou le score par défaut
            relevance_score = content_data.get('relevance_score', default_score)
            
            # Mettre à jour le score dans les données
            content_data['relevance_score'] = relevance_score
            content_data['is_important'] = is_important
            
            logger.info(f"Contenu accepté pour indexation [{lang}] [{relevance_score:.2f}]: {title} ({url})")
            
            return content_data
            
        except Exception as e:
            logger.error(f"Erreur lors du traitement du contenu: {str(e)}")
            # En cas d'erreur, on retourne le contenu original pour éviter les pertes
            return content_data
    
    def filter_content(self, content: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Filtre le contenu en utilisant GPT (version minimale)
        
        Args:
            content: Le contenu à filtrer
            context: Contexte supplémentaire pour le filtrage
            
        Returns:
            Le contenu filtré
        """
        # Version minimale - retourne le contenu sans modification
        logger.debug("Filtrage GPT appliqué (version minimale)")
        return content
    
    def is_relevant(self, content: str, threshold: float = 0.5) -> bool:
        """
        Détermine si le contenu est pertinent
        
        Args:
            content: Le contenu à évaluer
            threshold: Seuil de pertinence
            
        Returns:
            True si le contenu est pertinent
        """
        # Version minimale - considère tout le contenu comme pertinent
        return True if content and len(content.strip()) > 10 else False
    
    def categorize_content(self, content: str, categories: List[str]) -> str:
        """
        Catégorise le contenu parmi les catégories fournies
        
        Args:
            content: Le contenu à catégoriser
            categories: Liste des catégories disponibles
            
        Returns:
            La catégorie la plus probable
        """
        # Version minimale - retourne la première catégorie ou "général"
        return categories[0] if categories else "général"
