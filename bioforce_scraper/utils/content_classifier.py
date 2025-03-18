"""
Module pour classifier et filtrer le contenu extrait selon sa pertinence
"""
import logging
import re
from typing import Dict, Any, List, Tuple, Set, Optional

# Import absolus pour éviter les problèmes lorsque le module est importé depuis l'API
import sys
import pathlib
# Ajouter le répertoire parent au path pour pouvoir importer les modules
sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))

from bioforce_scraper.config import LOG_FILE
from bioforce_scraper.utils.logger import setup_logger

# Configuration du logger
logger = setup_logger(__name__, LOG_FILE)

class ContentClassifier:
    """
    Classe pour classifier et filtrer le contenu selon sa pertinence
    pour une base de connaissances éducative
    """
    
    def __init__(self):
        """
        Initialisation du classifieur de contenu
        """
        # Mots-clés importants pour le contexte éducatif de Bioforce
        self.important_keywords = [
            # Formation et compétences
            "formation", "compétence", "métier", "certification", "diplôme",
            "programme", "module", "cours", "session", "parcours", 
            "apprentissage", "enseignement", "éducation", "apprendre",
            
            # Candidature et admission
            "candidature", "admission", "inscription", "sélection", "prérequis",
            "dossier", "entretien", "test", "évaluation", "critère",
            
            # Financement
            "financement", "bourse", "aide", "coût", "frais", "tarif",
            "paiement", "subvention", "prise en charge", "remboursement",
            
            # Domaines humanitaires
            "humanitaire", "solidarité", "urgence", "crise", "développement",
            "réfugié", "aide", "secours", "intervention", "mission",
            "terrain", "projet", "ONG", "association", "international",
            
            # Métiers et fonctions
            "logistique", "ressources humaines", "coordination", "gestion", 
            "administration", "finance", "sécurité", "santé", "eau", 
            "assainissement", "nutrition", "protection", "abri",
            
            # FAQ et questions
            "faq", "question", "réponse", "information", "besoin", "aide"
        ]
        
        # Patterns pour identifier le contenu non pertinent
        self.non_relevant_patterns = [
            r"^\s*$",  # Contenu vide
            r"^.*?(cookies|confidentialité|mentions légales|copyright).*?$",  # Infos légales
            r"^.*?(404|page introuvable|erreur).*?$",  # Pages d'erreur
        ]
        
        # Seuils de pertinence
        self.min_content_length = 100  # Longueur minimale du contenu (caractères)
        self.min_keyword_occurrences = 1  # Nombre minimal de mots-clés présents
        self.min_relevance_score = 0.3  # Score minimal de pertinence (0 à 1)
    
    def classify_content(self, content: Dict[str, Any]) -> Tuple[bool, float, str]:
        """
        Classifie un contenu extrait et détermine sa pertinence
        
        Args:
            content: Dictionnaire contenant les métadonnées et le contenu extrait
            
        Returns:
            Tuple (est_pertinent, score_pertinence, catégorie)
        """
        # Extraire le titre et le contenu textuel
        title = content.get("title", "")
        text = content.get("content", "")
        url = content.get("url", "")
        
        # Vérifier si le contenu est vide ou trop court
        if not title or not text or len(text) < self.min_content_length:
            logger.debug(f"Contenu rejeté (trop court): {url}")
            return False, 0.0, "non_pertinent"
        
        # Vérifier les patterns de non-pertinence
        for pattern in self.non_relevant_patterns:
            if re.search(pattern, title, re.IGNORECASE) or re.search(pattern, text[:200], re.IGNORECASE):
                logger.debug(f"Contenu rejeté (pattern non pertinent): {url}")
                return False, 0.0, "non_pertinent"
        
        # Compter les occurrences de mots-clés importants
        keyword_count = 0
        matched_keywords = set()
        
        for keyword in self.important_keywords:
            # Rechercher dans le titre (avec un poids plus élevé)
            title_matches = len(re.findall(r'\b' + re.escape(keyword) + r'\b', title, re.IGNORECASE))
            keyword_count += title_matches * 3  # Triple poids pour les correspondances dans le titre
            
            if title_matches > 0:
                matched_keywords.add(keyword)
            
            # Rechercher dans le contenu
            content_matches = len(re.findall(r'\b' + re.escape(keyword) + r'\b', text, re.IGNORECASE))
            keyword_count += content_matches
            
            if content_matches > 0:
                matched_keywords.add(keyword)
        
        # Calculer le score de pertinence (normalisé entre 0 et 1)
        relevance_score = min(1.0, keyword_count / 20)
        
        # Déterminer la catégorie de contenu en fonction des mots-clés correspondants
        category = self._determine_category(matched_keywords, url)
        
        # Vérifier si le contenu atteint le seuil de pertinence
        is_relevant = (
            len(matched_keywords) >= self.min_keyword_occurrences and
            relevance_score >= self.min_relevance_score
        )
        
        if is_relevant:
            logger.debug(f"Contenu pertinent ({relevance_score:.2f}, {category}): {url}")
        else:
            logger.debug(f"Contenu non pertinent ({relevance_score:.2f}): {url}")
        
        return is_relevant, relevance_score, category
    
    def _determine_category(self, matched_keywords: Set[str], url: str) -> str:
        """
        Détermine la catégorie du contenu en fonction des mots-clés correspondants
        
        Args:
            matched_keywords: Ensemble des mots-clés trouvés dans le contenu
            url: URL du contenu
            
        Returns:
            Catégorie du contenu
        """
        # Définir des ensembles de mots-clés par catégorie
        formation_keywords = {"formation", "programme", "module", "cours", "compétence", "métier", "diplôme", "certification"}
        candidature_keywords = {"candidature", "admission", "inscription", "sélection", "prérequis", "dossier"}
        financement_keywords = {"financement", "bourse", "aide", "coût", "frais", "tarif", "paiement"}
        faq_keywords = {"faq", "question", "réponse"}
        
        # Vérifier l'URL pour des indices supplémentaires
        if "/formation/" in url or "/learn/" in url:
            return "formation"
        elif "/candidature/" in url:
            return "candidature"
        elif "/financement/" in url or "/financer-" in url:
            return "financement"
        elif "/faq/" in url or "/questions-" in url:
            return "faq"
        
        # Déterminer la catégorie en fonction des mots-clés correspondants
        # (en comptant les correspondances par catégorie)
        category_scores = {
            "formation": len(matched_keywords.intersection(formation_keywords)),
            "candidature": len(matched_keywords.intersection(candidature_keywords)),
            "financement": len(matched_keywords.intersection(financement_keywords)),
            "faq": len(matched_keywords.intersection(faq_keywords)),
        }
        
        # Choisir la catégorie avec le score le plus élevé
        max_score = max(category_scores.values())
        if max_score > 0:
            for category, score in category_scores.items():
                if score == max_score:
                    return category
        
        # Par défaut, utiliser "général"
        return "général"
    
    def should_index_content(self, content: Dict[str, Any]) -> bool:
        """
        Détermine si un contenu doit être indexé dans la base de connaissances
        
        Args:
            content: Dictionnaire contenant les métadonnées et le contenu extrait
            
        Returns:
            True si le contenu doit être indexé, False sinon
        """
        is_relevant, relevance_score, category = self.classify_content(content)
        
        if is_relevant:
            # Ajouter la catégorie et le score au contenu
            content["category"] = category
            content["relevance_score"] = relevance_score
            return True
        
        return False
