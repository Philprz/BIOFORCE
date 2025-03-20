"""
Module de gestion des embeddings pour la base de connaissances
"""
import numpy as np
from typing import List, Optional

import openai
from openai import AsyncOpenAI

from bioforce_scraper.config import (OPENAI_API_KEY, EMBEDDING_MODEL, VECTOR_SIZE, LOG_FILE, COMPLETION_MODEL)
from bioforce_scraper.utils.logger import setup_logger

# Configuration du logger
logger = setup_logger(__name__, LOG_FILE)

# Configuration d'OpenAI
openai.api_key = OPENAI_API_KEY
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

async def generate_embeddings(text: str) -> Optional[List[float]]:
    """
    Génère un embedding pour un texte donné en utilisant OpenAI
    
    Args:
        text: Texte à encoder
        
    Returns:
        Vecteur d'embedding ou None en cas d'erreur
    """
    if not OPENAI_API_KEY:
        logger.warning("Clé API OpenAI non configurée. Utilisation d'embeddings aléatoires.")
        return generate_random_embedding()
    
    try:
        # Vérifier si le texte est fourni
        if not text or not isinstance(text, str):
            logger.error(f"Texte invalide fourni pour la génération d'embedding: {type(text)}")
            return None
            
        # S'assurer que le texte n'est pas trop long (max 8191 tokens pour OpenAI)
        if len(text) > 25000:  # Estimation grossière, à ajuster
            text = text[:25000]
            logger.warning("Texte tronqué à 25000 caractères pour l'embedding")
            
        # Normaliser le texte (retirer les espaces multiples, etc.)
        text = " ".join(text.split())
        
        # Limiter la taille du texte pour éviter des coûts excessifs
        truncated_text = text[:8000]
        
        # Générer l'embedding
        response = await client.embeddings.create(
            input=truncated_text,
            model=EMBEDDING_MODEL
        )
        
        # Récupérer le vecteur d'embedding
        embedding = response.data[0].embedding
        
        # Normaliser explicitement le vecteur pour garantir la compatibilité avec la recherche cosinus
        embedding_np = np.array(embedding)
        norm = np.linalg.norm(embedding_np)
        if norm > 0:
            normalized_embedding = (embedding_np / norm).tolist()
            return normalized_embedding
        
        return embedding
        
    except Exception as e:
        logger.error(f"Erreur lors de la génération de l'embedding: {e}")
        
        # En cas d'erreur, générer un embedding aléatoire
        return generate_random_embedding()

def generate_random_embedding(size: int = VECTOR_SIZE) -> List[float]:
    """
    Génère un embedding aléatoire pour les tests ou en cas d'erreur
    
    Args:
        size: Taille du vecteur d'embedding
        
    Returns:
        Vecteur d'embedding aléatoire normalisé
    """
    # Générer un vecteur aléatoire et le normaliser
    vector = np.random.rand(size)
    normalized_vector = vector / np.linalg.norm(vector)
    
    return normalized_vector.tolist()

async def generate_batch_embeddings(texts: List[str]) -> List[Optional[List[float]]]:
    """
    Génère des embeddings pour une liste de textes
    
    Args:
        texts: Liste de textes à encoder
        
    Returns:
        Liste de vecteurs d'embedding
    """
    embeddings = []
    
    for text in texts:
        embedding = await generate_embeddings(text)
        embeddings.append(embedding)
    
    return embeddings

async def generate_summary(text: str, max_tokens: int = 200) -> str:
    """
    Génère un résumé d'un texte en utilisant OpenAI
    
    Args:
        text: Texte à résumer
        max_tokens: Nombre maximum de tokens pour la réponse
        
    Returns:
        Résumé du texte
    """
    if not OPENAI_API_KEY:
        logger.warning("Clé API OpenAI non configurée. Impossible de générer un résumé.")
        return ""
    
    try:
        # Limiter la taille du texte
        truncated_text = text[:4000]
        
        # Générer le résumé
        response = await client.chat.completions.create(
            model=COMPLETION_MODEL,
            messages=[
                {"role": "system", "content": "Tu es un assistant qui résume du contenu de manière concise et factuelle."},
                {"role": "user", "content": f"Résume le texte suivant en français en moins de 100 mots:\n\n{truncated_text}"}
            ],
            max_tokens=max_tokens,
            temperature=0.3
        )
        
        summary = response.choices[0].message.content.strip()
        return summary
        
    except Exception as e:
        logger.error(f"Erreur lors de la génération du résumé: {e}")
        return ""
