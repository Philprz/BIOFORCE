"""
Script simplifié pour remplir uniquement la collection BIOFORCE avec des FAQ
"""
import os
import asyncio
import json
from datetime import datetime
from typing import List, Dict, Any

import aiohttp
from bs4 import BeautifulSoup

from bioforce_scraper.config import QDRANT_COLLECTION, VECTOR_SIZE, LOG_DIR
from bioforce_scraper.utils.qdrant_connector import QdrantConnector
from bioforce_scraper.utils.embeddings import generate_embeddings
from bioforce_scraper.utils.logger import setup_logger

# Configuration du logger
log_file = os.path.join(LOG_DIR, f"rebuild_faq_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
logger = setup_logger(__name__, log_file)

# Liste des URLs de FAQ à traiter
FAQ_URLS = [
    "https://www.bioforce.org/question/sed-ut-perspiciatis-unde-omnis-iste-natus-error-sit-voluptatem-accusantium-doloremque-laudantium-totam-rem-2/",
    "https://www.bioforce.org/question/quelle-est-la-specificite-des-formations-bioforce/",
    "https://www.bioforce.org/question/qui-sont-les-intervenants-formateurs-de-bioforce/",
    "https://www.bioforce.org/question/quels-sont-les-parcours-profils-des-formateurs/",
    "https://www.bioforce.org/question/comment-fonctionne-le-cpf-de-transition-professionnelle-anciennement-cif/",
    "https://www.bioforce.org/question/les-supports-de-cours-me-sont-ils-communiques/",
    "https://www.bioforce.org/question/comment-venir-jusquau-lieu-de-formation/",
    "https://www.bioforce.org/question/quest-ce-quune-formation-bioforce-en-e-learning/",
    "https://www.bioforce.org/question/quest-ce-que-biomoodle/",
    "https://www.bioforce.org/question/quelle-est-la-difference-entre-une-formation-bioforce-en-e-learning-et-une-formation-en-presentiel/"
]

class FaqCollectionBuilder:
    """
    Classe pour reconstruire uniquement la collection FAQ
    """
    def __init__(self):
        self.qdrant = QdrantConnector(collection_name=QDRANT_COLLECTION, is_full_site=False)
        self.total_faq = 0
        self.successful_faq = 0
        
    async def recreate_collection(self):
        """
        Recrée la collection Qdrant et la remplit avec les FAQ
        """
        logger.info("Début de la reconstruction de la collection BIOFORCE avec les FAQ...")
        
        # Recréer la collection
        self._recreate_collection()
        
        # Traiter les URLs de FAQ
        await self._process_faq_urls()
        
        # Afficher les statistiques
        self._print_stats()
        
        logger.info("Reconstruction de la collection terminée.")
        
    def _recreate_collection(self):
        """
        Supprime et recrée la collection Qdrant
        """
        logger.info(f"Recréation de la collection {QDRANT_COLLECTION}...")
        
        try:
            # Supprimer la collection si elle existe
            collections = self.qdrant.client.get_collections().collections
            collection_names = [c.name for c in collections]
            
            if QDRANT_COLLECTION in collection_names:
                logger.info(f"Suppression de la collection existante {QDRANT_COLLECTION}...")
                self.qdrant.client.delete_collection(collection_name=QDRANT_COLLECTION)
                
            # Créer la collection
            self.qdrant.ensure_collection(vector_size=VECTOR_SIZE)
            logger.info(f"Collection {QDRANT_COLLECTION} créée avec succès.")
            
        except Exception as e:
            logger.error(f"Erreur lors de la recréation de la collection {QDRANT_COLLECTION}: {e}")
            raise
    
    async def _process_faq_urls(self):
        """
        Traite les URLs de FAQ pour extraire et indexer le contenu
        """
        logger.info(f"Traitement de {len(FAQ_URLS)} URLs de FAQ...")
        
        async with aiohttp.ClientSession() as session:
            for url in FAQ_URLS:
                try:
                    self.total_faq += 1
                    logger.info(f"Traitement de la FAQ: {url}")
                    
                    # Extraire le contenu de la page
                    faq_item = await self._extract_faq_content(session, url)
                    
                    if faq_item:
                        # Indexer dans Qdrant
                        await self._index_faq(faq_item)
                        self.successful_faq += 1
                        
                except Exception as e:
                    logger.error(f"Erreur lors du traitement de la FAQ {url}: {e}")
    
    async def _extract_faq_content(self, session: aiohttp.ClientSession, url: str) -> Dict[str, Any]:
        """
        Extrait le contenu d'une page FAQ
        """
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    logger.error(f"Erreur lors de la requête HTTP: {response.status}")
                    return None
                
                html = await response.text()
                
                # Extraire le contenu avec BeautifulSoup
                soup = BeautifulSoup(html, 'html.parser')
                
                # Extraire le titre (question)
                title_tag = soup.find('h1', class_='question-title')
                if not title_tag:
                    title_tag = soup.find('h1')
                    
                title = title_tag.get_text().strip() if title_tag else "Question sans titre"
                
                # Extraire le contenu (réponse)
                content_div = soup.find('div', class_='question-content')
                if not content_div:
                    content_div = soup.find('div', class_='entry-content')
                    
                if content_div:
                    # Nettoyer le contenu HTML
                    paragraphs = content_div.find_all(['p', 'ul', 'ol', 'li', 'h2', 'h3', 'h4'])
                    content = " ".join([p.get_text().strip() for p in paragraphs])
                else:
                    content = "Contenu non trouvé"
                
                # Créer l'objet FAQ
                faq_item = {
                    "title": title,
                    "content": content,
                    "url": url,
                    "timestamp": datetime.now().isoformat(),
                    "language": "fr",
                    "category": "faq",
                    "content_type": "html",
                    "is_faq": True,
                    "relevance_score": 0.9  # Score élevé pour les FAQ
                }
                
                logger.info(f"FAQ extraite avec succès: {title}")
                return faq_item
                
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction de la FAQ {url}: {e}")
            return None
    
    async def _index_faq(self, faq_item: Dict[str, Any]):
        """
        Indexe un élément FAQ dans Qdrant
        """
        try:
            # Générer l'embedding
            embedding = await generate_embeddings(faq_item["content"])
            
            if not embedding:
                logger.error(f"Échec de génération d'embedding pour {faq_item['url']}")
                return
            
            # Préparer les métadonnées
            payload = {
                "title": faq_item["title"],
                "content": faq_item["content"],
                "url": faq_item["url"],
                "source_url": faq_item["url"],
                "type": "html",
                "category": "faq",
                "timestamp": faq_item["timestamp"],
                "language": "fr",
                "relevance_score": 0.9,
                "is_faq": True
            }
            
            # Générer un ID unique basé sur l'URL
            import hashlib
            doc_id = hashlib.md5(faq_item["url"].encode()).hexdigest()
            
            # Indexer dans Qdrant avec la méthode upsert_document
            success = self.qdrant.upsert_document(id=doc_id, vector=embedding, payload=payload)
            if success:
                logger.info(f"FAQ indexée avec succès: {faq_item['title']}")
            else:
                logger.error(f"Échec de l'indexation pour: {faq_item['title']}")
            
        except Exception as e:
            logger.error(f"Erreur lors de l'indexation de la FAQ: {e}")
    
    def _print_stats(self):
        """
        Affiche les statistiques de la reconstruction
        """
        logger.info("=== Statistiques de reconstruction des FAQ ===")
        logger.info(f"Total de FAQ traitées: {self.total_faq}")
        logger.info(f"FAQ indexées avec succès: {self.successful_faq}")
        logger.info(f"Taux de réussite: {(self.successful_faq / self.total_faq * 100) if self.total_faq > 0 else 0:.2f}%")
        logger.info("==============================================")


async def main():
    """Fonction principale"""
    start_time = datetime.now()
    logger.info(f"Début du processus de reconstruction FAQ: {start_time}")
    
    builder = FaqCollectionBuilder()
    await builder.recreate_collection()
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    logger.info(f"Fin du processus de reconstruction: {end_time}")
    logger.info(f"Durée totale: {duration:.2f} secondes")

if __name__ == "__main__":
    asyncio.run(main())
