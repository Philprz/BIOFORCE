"""
Script pour reconstruire les collections Qdrant BIOFORCE et BIOFORCE_ALL
avec le nouveau système de filtrage GPT-4o-mini
"""
import os
import asyncio
import json
import random
from datetime import datetime
from typing import List, Dict, Any

from bioforce_scraper.config import (
    DATA_DIR, QDRANT_COLLECTION, QDRANT_COLLECTION_ALL,
    VECTOR_SIZE, LOG_DIR
)
from bioforce_scraper.utils.qdrant_connector import QdrantConnector
from bioforce_scraper.utils.embeddings import generate_embeddings
from bioforce_scraper.integration.gpt_filter_integration import GPTFilterIntegration
from bioforce_scraper.utils.logger import setup_logger

# Configuration du logger
log_file = os.path.join(LOG_DIR, f"rebuild_collections_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
logger = setup_logger(__name__, log_file)

# Paramètres d'échantillonnage pour les tests
SAMPLE_SIZE = 10  # Nombre de pages à traiter pour le test
TEST_MODE = True  # Mode test activé

class CollectionsRebuild:
    """
    Classe pour reconstruire les collections Qdrant avec le filtrage GPT
    """
    def __init__(self):
        self.gpt_filter = GPTFilterIntegration()
        self.qdrant_bioforce = QdrantConnector(collection_name=QDRANT_COLLECTION, is_full_site=False)
        self.qdrant_bioforce_all = QdrantConnector(collection_name=QDRANT_COLLECTION_ALL, is_full_site=True)
        
        # Statistiques
        self.total_documents = 0
        self.filtered_documents = 0
        self.indexed_documents = 0
        self.total_faq_items = 0
        self.filtered_faq_items = 0
        
    async def recreate_collections(self):
        """
        Recrée les collections Qdrant et les remplit avec le contenu filtré
        """
        logger.info("Début de la reconstruction des collections Qdrant...")
        
        # Recréer les collections
        self._recreate_collection(self.qdrant_bioforce)
        self._recreate_collection(self.qdrant_bioforce_all)
        
        # Charger les données existantes
        data_files = self._get_data_files()
        
        # Filtrer et indexer les données
        await self._process_data_files(data_files)
        
        # Afficher les statistiques
        self._print_stats()
        
        logger.info("Reconstruction des collections terminée avec succès.")
        
    def _recreate_collection(self, qdrant_connector: QdrantConnector):
        """
        Supprime et recrée une collection Qdrant
        """
        collection_name = qdrant_connector.collection_name
        logger.info(f"Recréation de la collection {collection_name}...")
        
        try:
            # Supprimer la collection si elle existe
            collections = qdrant_connector.client.get_collections().collections
            collection_names = [c.name for c in collections]
            
            if collection_name in collection_names:
                logger.info(f"Suppression de la collection existante {collection_name}...")
                qdrant_connector.client.delete_collection(collection_name=collection_name)
                
            # Créer la collection
            qdrant_connector.ensure_collection(vector_size=VECTOR_SIZE)
            logger.info(f"Collection {collection_name} créée avec succès.")
            
        except Exception as e:
            logger.error(f"Erreur lors de la recréation de la collection {collection_name}: {e}")
            raise
    
    def _get_data_files(self) -> List[str]:
        """
        Récupère la liste des fichiers de données JSON
        """
        data_files = []
        for root, _, files in os.walk(DATA_DIR):
            for file in files:
                if file.endswith('.json'):
                    data_files.append(os.path.join(root, file))
        
        logger.info(f"Nombre de fichiers de données trouvés: {len(data_files)}")
        return data_files
    
    async def _process_data_files(self, data_files: List[str]):
        """
        Traite les fichiers de données pour les filtrer et les indexer
        """
        if TEST_MODE:
            logger.info(f"Mode test activé, traitement de {SAMPLE_SIZE} pages...")
            if len(data_files) > SAMPLE_SIZE:
                # Assurer un mix de types de contenus dans l'échantillon
                html_files = [f for f in data_files if 'html' in f.lower()]
                pdf_files = [f for f in data_files if 'pdf' in f.lower()]
                faq_files = [f for f in data_files if 'faq' in f.lower()]
                
                # Sélectionner un échantillon équilibré
                sample_files = []
                
                # Prioriser les FAQs
                if faq_files:
                    sample_files.extend(random.sample(faq_files, min(3, len(faq_files))))
                
                # Ajouter des PDFs
                if pdf_files:
                    sample_files.extend(random.sample(pdf_files, min(2, len(pdf_files))))
                
                # Compléter avec des fichiers HTML
                remaining = SAMPLE_SIZE - len(sample_files)
                if remaining > 0 and html_files:
                    sample_files.extend(random.sample(html_files, min(remaining, len(html_files))))
                
                # Compléter si nécessaire
                remaining = SAMPLE_SIZE - len(sample_files)
                if remaining > 0:
                    other_files = [f for f in data_files if f not in sample_files]
                    if other_files:
                        sample_files.extend(random.sample(other_files, min(remaining, len(other_files))))
                
                data_files = sample_files
                logger.info(f"Échantillon équilibré: FAQs: {sum(1 for f in data_files if 'faq' in f.lower())}, "
                           f"PDFs: {sum(1 for f in data_files if 'pdf' in f.lower())}, "
                           f"Autres: {sum(1 for f in data_files if 'faq' not in f.lower() and 'pdf' not in f.lower())}")
            else:
                logger.info(f"Nombre de fichiers insuffisant ({len(data_files)}), traitement de tous les fichiers")
        
        for file_path in data_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    document = json.load(f)
                
                self.total_documents += 1
                
                # Journaliser le document en cours de traitement
                logger.info(f"Traitement du document: {file_path}")
                
                # Filtrer le document avec GPT
                if 'is_faq' in document and document.get('is_faq', False):
                    # Traiter comme FAQ
                    self.total_faq_items += 1
                    filtered_item = await self._process_faq_item(document)
                    if filtered_item:
                        self.filtered_faq_items += 1
                        await self._index_document(filtered_item)
                else:
                    # Traiter comme contenu standard
                    is_html = document.get('content_type', '') == 'html'
                    if is_html:
                        filtered_content = await self.gpt_filter.process_html_content(document)
                    else:
                        # Traiter comme PDF
                        try:
                            result = await self.gpt_filter.process_pdf_content(document)
                            if result:
                                filtered_content = result  # result est déjà le document filtré ou None
                            else:
                                filtered_content = None
                        except Exception as e:
                            logger.error(f"Erreur lors du traitement PDF: {e}")
                            filtered_content = None
                    
                    if filtered_content:
                        self.filtered_documents += 1
                        await self._index_document(filtered_content)
                    
            except Exception as e:
                logger.error(f"Erreur lors du traitement du fichier {file_path}: {e}")
    
    async def _process_faq_item(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Traite un élément FAQ pour le filtrage et retourne le contenu filtré
        """
        try:
            # Vérifier que le document contient les champs nécessaires
            if not document.get('title') or not document.get('content'):
                logger.warning(f"FAQ incomplète, ignorée: {document.get('url', 'URL inconnue')}")
                return None
                
            # Créer un format approprié pour le filtrage FAQ
            faq_item = {
                "question": document.get('title', ''),
                "answer": document.get('content', ''),
                "url": document.get('url', '')
            }
            
            # Filtrer avec GPT
            kept_items, _ = await self.gpt_filter.content_filter.filter_faq_content([faq_item])
            
            if kept_items:
                # Réintégrer dans le format du document
                document['content'] = kept_items[0]['answer']
                # S'assurer que le document a une valeur de pertinence élevée
                document['relevance_score'] = max(document.get('relevance_score', 0.0), 0.8)
                document['language'] = document.get('language', 'fr')
                document['category'] = document.get('category', 'faq')
                return document
            
            return None
        except Exception as e:
            logger.error(f"Erreur lors du traitement de la FAQ {document.get('url', 'URL inconnue')}: {e}")
            return None
    
    async def _index_document(self, document: Dict[str, Any]):
        """
        Indexe un document dans les collections Qdrant appropriées
        """
        try:
            # S'assurer que le contenu n'est pas vide
            if not document.get('content'):
                logger.warning(f"Contenu vide pour {document.get('url', 'URL inconnue')}, ignoré")
                return

            # Générer l'embedding
            embedding = await generate_embeddings(document['content'])
            
            if not embedding:
                logger.error(f"Échec de génération d'embedding pour {document.get('url', 'URL inconnue')}")
                return
            
            # Préparer les métadonnées
            payload = {
                "title": document.get('title', ''),
                "content": document.get('content', ''),
                "url": document.get('url', ''),
                "source_url": document.get('url', ''),
                "type": document.get('content_type', 'html'),
                "category": document.get('category', 'general'),
                "timestamp": document.get('timestamp', datetime.now().isoformat()),
                "language": document.get('language', 'fr'),
                "relevance_score": document.get('relevance_score', 0.7),
                "is_faq": document.get('is_faq', False)
            }
            
            # Indexer dans les deux collections
            self.qdrant_bioforce.upsert(embedding, payload)
            self.qdrant_bioforce_all.upsert(embedding, payload)
            
            self.indexed_documents += 1
            
            if self.indexed_documents % 10 == 0:
                logger.info(f"Progression: {self.indexed_documents} documents indexés")
            
        except Exception as e:
            logger.error(f"Erreur lors de l'indexation du document: {e}")
            if document and 'url' in document:
                logger.error(f"URL du document en erreur: {document['url']}")
    
    def _print_stats(self):
        """
        Affiche les statistiques de la reconstruction
        """
        logger.info("=== Statistiques de reconstruction ===")
        logger.info(f"Total de documents traités: {self.total_documents}")
        logger.info(f"Documents filtrés (conservés après filtrage): {self.filtered_documents}")
        logger.info(f"Documents indexés: {self.indexed_documents}")
        logger.info(f"Éléments FAQ traités: {self.total_faq_items}")
        logger.info(f"Éléments FAQ filtrés (conservés): {self.filtered_faq_items}")
        logger.info(f"Taux de filtrage: {(self.total_documents - self.filtered_documents) / self.total_documents * 100:.2f}%")
        logger.info("=======================================")

async def main():
    """Fonction principale"""
    start_time = datetime.now()
    logger.info(f"Début du processus de reconstruction: {start_time}")
    
    rebuilder = CollectionsRebuild()
    await rebuilder.recreate_collections()
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    logger.info(f"Fin du processus de reconstruction: {end_time}")
    logger.info(f"Durée totale: {duration:.2f} secondes")

if __name__ == "__main__":
    asyncio.run(main())
