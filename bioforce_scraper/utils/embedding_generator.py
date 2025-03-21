"""
Module de génération d'embeddings pour le projet Bioforce.
Ce module réexporte la fonction generate_embeddings du module embeddings.py
"""

# Réutilisation de la fonction existante pour éviter la duplication de code
from bioforce_scraper.utils.embeddings import generate_embeddings, generate_batch_embeddings

# Export direct des fonctions depuis embeddings.py
__all__ = ['generate_embeddings', 'generate_batch_embeddings']
