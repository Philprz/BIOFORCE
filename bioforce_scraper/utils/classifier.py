"""
Module pour la classification automatique du contenu
"""
import re
from typing import Dict, List

import sys
import pathlib
# Ajouter le répertoire parent au path pour pouvoir importer les modules
sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))

from bioforce_scraper.config import CONTENT_CATEGORIES, LOG_FILE
from bioforce_scraper.utils.logger import setup_logger

logger = setup_logger(__name__, LOG_FILE)

# Mots-clés par catégorie
CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    'formation': [
        'formation', 'programme', 'cours', 'enseignement', 'parcours', 
        'cursus', 'apprentissage', 'module', 'compétence', 'certification',
        'diplôme', 'bachelor', 'formation professionnelle', 'formation continue',
        'validation', 'acquis', 'expérience', 'VAE', 'bac+', 'enseignant'
    ],
    'admission': [
        'admission', 'inscription', 'candidature', 'postuler', 'dossier', 
        'sélection', 'recrutement', 'entretien', 'critère', 'condition', 
        'prérequis', 'éligibilité', 'acceptation', 'test', 'examen', 
        'candidat', 'postulant', 'recrutement'
    ],
    'financement': [
        'financement', 'bourse', 'aide', 'frais', 'coût', 'tarif', 'prix',
        'paiement', 'échéancier', 'redevance', 'payer', 'règlement',
        'subvention', 'budget', 'opco', 'pôle emploi', 'CPF', 'RNCP', 'CIF'
    ],
    'logistique': [
        'logistique', 'logement', 'hébergement', 'transport', 'installation',
        'déplacement', 'campus', 'résidence', 'accès', 'adresse', 'site',
        'localisation', 'restauration', 'cantine', 'visa', 'déménagement'
    ],
    'faq': [
        'faq', 'question', 'réponse', 'foire aux questions', 'souvent',
        'demandé', 'interrogation', 'aide', 'assistance', 'conseil',
        'problème', 'solution', 'comment', 'pourquoi', 'quand', 'où', 'qui'
    ],
    'processus': [
        'processus', 'étape', 'procédure', 'démarche', 'méthode', 'approche',
        'planning', 'calendrier', 'chronologie', 'déroulement', 'cycle',
        'progression', 'avancement', 'phase', 'workflow', 'instruction'
    ],
    'informations_pratiques': [
        'information', 'pratique', 'guide', 'astuce', 'conseil', 'recommandation',
        'suggestion', 'document', 'formulaire', 'déclaration', 'attestation',
        'certificat', 'référence', 'document', 'horaire', 'ouverture', 'fermeture'
    ]
}

def classify_content(url: str, title: str, content: str) -> str:
    """
    Classifie le contenu en fonction des mots-clés
    
    Args:
        url: URL de la page
        title: Titre de la page
        content: Contenu textuel de la page
        
    Returns:
        Catégorie du contenu
    """
    # Vérifier d'abord l'URL pour des indices clairs
    url_category = classify_by_url(url)
    if url_category:
        return url_category
    
    # Combiner le titre et le début du contenu pour la classification
    classification_text = (title + " " + content[:1000]).lower()
    
    # Compter les occurrences de mots-clés par catégorie
    category_scores: Dict[str, int] = {category: 0 for category in CONTENT_CATEGORIES}
    
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            # Plus de poids pour les mots-clés dans le titre
            if keyword.lower() in title.lower():
                category_scores[category] += 3
            
            # Compter les occurrences dans le texte
            count = len(re.findall(r'\b' + re.escape(keyword.lower()) + r'\b', classification_text))
            category_scores[category] += count
    
    # Trouver la catégorie avec le score le plus élevé
    max_score = 0
    best_category = 'général'  # Catégorie par défaut
    
    for category, score in category_scores.items():
        if score > max_score:
            max_score = score
            best_category = category
    
    # Si aucune catégorie ne se démarque clairement, utiliser 'général'
    if max_score < 3:
        return 'général'
    
    return best_category

def classify_by_url(url: str) -> str:
    """
    Classifie en fonction de l'URL
    
    Args:
        url: URL à classifier
        
    Returns:
        Catégorie ou None si pas de correspondance claire
    """
    url_lower = url.lower()
    
    # Patterns spécifiques dans l'URL
    url_patterns = {
        'formation': ['/formation/', '/learn/', '/cursus/', '/programme/'],
        'admission': ['/admission/', '/candidature/', '/postuler/', '/inscription/'],
        'financement': ['/financement/', '/tarif/', '/prix/', '/bourse/', '/cout/'],
        'logistique': ['/logement/', '/campus/', '/localisation/', '/acces/'],
        'faq': ['/faq/', '/questions/', '/aide/'],
        'processus': ['/processus/', '/procedure/', '/etape/', '/demarche/'],
        'informations_pratiques': ['/info', '/pratique/', '/contact/', '/guide/']
    }
    
    for category, patterns in url_patterns.items():
        for pattern in patterns:
            if pattern in url_lower:
                return category
    
    return ""
