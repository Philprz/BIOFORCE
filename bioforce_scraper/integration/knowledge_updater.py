"""
Module d'intégration principal pour mettre à jour la base de connaissances du chatbot
"""
import json
import os
from datetime import datetime

from integration.qdrant_connector import QdrantConnector
from main import BioforceScraperMain
from utils.content_tracker import ContentTracker
import sys
import pathlib
# Ajouter le répertoire parent au path pour pouvoir importer les modules
sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))
from bioforce_scraper.config import DATA_DIR, LOG_FILE
from bioforce_scraper.utils.logger import setup_logger

logger = setup_logger(__name__, LOG_FILE)

class KnowledgeUpdater:
    """
    Classe pour gérer la mise à jour de la base de connaissances du chatbot
    """
    
    def __init__(self, qdrant_url=None, qdrant_api_key=None, collection_name="bioforce_knowledge"):
        """
        Initialise le metteur à jour de connaissances
        
        Args:
            qdrant_url: URL du serveur Qdrant
            qdrant_api_key: Clé API pour Qdrant
            collection_name: Nom de la collection Qdrant
        """
        self.scraper = BioforceScraperMain()
        self.content_tracker = ContentTracker()
        self.qdrant = QdrantConnector(
            url=qdrant_url,
            api_key=qdrant_api_key,
            collection_name=collection_name
        )
        
        # S'assurer que la collection Qdrant existe
        if not self.qdrant.ensure_collection():
            logger.error("Impossible d'initialiser la collection Qdrant")
    
    async def sync_content_with_qdrant(self):
        """
        Synchronise les contenus déjà extraits avec Qdrant
        
        Returns:
            Tuple (nb_documents_ajoutés, nb_documents_mis_à_jour)
        """
        logger.info("Synchronisation des contenus existants avec Qdrant...")
        
        # Obtenir toutes les URLs dans Qdrant
        qdrant_urls = set(self.qdrant.get_all_urls())
        logger.info(f"URLs dans Qdrant: {len(qdrant_urls)}")
        
        # Obtenir tous les enregistrements dans le tracker
        tracker_records = self.content_tracker.get_all_content_records()
        logger.info(f"Enregistrements dans le tracker: {len(tracker_records)}")
        
        # Parcourir les enregistrements du tracker
        added = 0
        updated = 0
        
        for record in tracker_records:
            url = record['url']
            data_file = record.get('data_file')
            
            if not data_file or not os.path.exists(data_file):
                logger.warning(f"Fichier de données introuvable pour {url}: {data_file}")
                continue
            
            try:
                # Charger les données du document
                with open(data_file, 'r', encoding='utf-8') as f:
                    document = json.load(f)
                
                # Vérifier si l'URL est déjà dans Qdrant
                if url in qdrant_urls:
                    # Mise à jour
                    result = self.qdrant.upsert_document_chunks(document)
                    if result:
                        updated += 1
                        logger.info(f"Document mis à jour dans Qdrant: {url}")
                else:
                    # Ajout
                    result = self.qdrant.upsert_document_chunks(document)
                    if result:
                        added += 1
                        logger.info(f"Document ajouté à Qdrant: {url}")
            
            except Exception as e:
                logger.error(f"Erreur lors de la synchronisation de {url}: {e}")
        
        logger.info(f"Synchronisation terminée. Ajoutés: {added}, Mis à jour: {updated}")
        return added, updated
    
    async def update_knowledge_base(self):
        """
        Met à jour la base de connaissances en lançant le scraper et en envoyant les nouveaux contenus à Qdrant
        
        Returns:
            Dictionnaire avec les statistiques de mise à jour
        """
        logger.info("Démarrage de la mise à jour de la base de connaissances...")
        
        # Exécuter le scraper
        scraper_results = await self.scraper.run()
        
        # Analyser les résultats du scraper
        new_content = scraper_results.get('new_content', [])
        updated_content = scraper_results.get('updated_content', [])
        
        # Statistiques
        stats = {
            "scraper": {
                "new": len(new_content),
                "updated": len(updated_content),
                "unchanged": scraper_results.get('unchanged_count', 0),
                "total": scraper_results.get('total_count', 0)
            },
            "qdrant": {
                "added": 0,
                "updated": 0,
                "failed": 0
            },
            "timestamp": datetime.now().isoformat()
        }
        
        # Traiter les nouveaux contenus
        added = 0
        for content_info in new_content:
            url = content_info.get('url')
            data_file = content_info.get('data_file')
            
            if data_file and os.path.exists(data_file):
                try:
                    with open(data_file, 'r', encoding='utf-8') as f:
                        document = json.load(f)
                    
                    result = self.qdrant.upsert_document_chunks(document)
                    if result:
                        added += 1
                        logger.info(f"Nouveau contenu ajouté à Qdrant: {url}")
                    else:
                        stats["qdrant"]["failed"] += 1
                        logger.error(f"Échec de l'ajout du document à Qdrant: {url}")
                
                except Exception as e:
                    stats["qdrant"]["failed"] += 1
                    logger.error(f"Erreur lors du traitement du nouveau contenu {url}: {e}")
        
        stats["qdrant"]["added"] = added
        
        # Traiter les contenus mis à jour
        updated = 0
        for content_info in updated_content:
            url = content_info.get('url')
            data_file = content_info.get('data_file')
            
            if data_file and os.path.exists(data_file):
                try:
                    with open(data_file, 'r', encoding='utf-8') as f:
                        document = json.load(f)
                    
                    result = self.qdrant.upsert_document_chunks(document)
                    if result:
                        updated += 1
                        logger.info(f"Contenu mis à jour dans Qdrant: {url}")
                    else:
                        stats["qdrant"]["failed"] += 1
                        logger.error(f"Échec de la mise à jour du document dans Qdrant: {url}")
                
                except Exception as e:
                    stats["qdrant"]["failed"] += 1
                    logger.error(f"Erreur lors du traitement du contenu mis à jour {url}: {e}")
        
        stats["qdrant"]["updated"] = updated
        
        # Sauvegarder les statistiques dans un fichier
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stats_file = os.path.join(DATA_DIR, f"update_stats_{timestamp}.json")
        
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Mise à jour terminée. Ajoutés: {added}, Mis à jour: {updated}")
        logger.info(f"Statistiques sauvegardées dans: {stats_file}")
        
        return stats
    
    async def perform_initial_sync(self):
        """
        Effectue une synchronisation initiale complète entre le tracker de contenu et Qdrant
        
        Returns:
            Dictionnaire avec les statistiques de synchronisation
        """
        logger.info("Démarrage de la synchronisation initiale...")
        
        # Synchroniser les contenus existants
        added, updated = await self.sync_content_with_qdrant()
        
        stats = {
            "qdrant": {
                "added": added,
                "updated": updated
            },
            "timestamp": datetime.now().isoformat()
        }
        
        # Sauvegarder les statistiques dans un fichier
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stats_file = os.path.join(DATA_DIR, f"initial_sync_stats_{timestamp}.json")
        
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Synchronisation initiale terminée. Ajoutés: {added}, Mis à jour: {updated}")
        logger.info(f"Statistiques sauvegardées dans: {stats_file}")
        
        return stats
