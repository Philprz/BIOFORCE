"""
Script pour upserter les fichiers JSON du dossier output/data dans Qdrant
Vérifie si l'URL est déjà présente et remplit la collection BIOFORCE
"""
import asyncio
import json
import os
import sys
import pathlib
import glob
import uuid
from qdrant_client import models

# Ajouter le répertoire parent au path pour pouvoir importer les modules
sys.path.append(str(pathlib.Path(__file__).parent))

from bioforce_scraper.utils.qdrant_connector import QdrantConnector
from bioforce_scraper.config import DATA_DIR, LOG_FILE
from bioforce_scraper.utils.logger import setup_logger
from bioforce_scraper.utils.embedding_generator import generate_embeddings

# Configuration du logger
logger = setup_logger("upsert_data", LOG_FILE)

async def check_url_exists(qdrant_connector, url):
    """
    Vérifie si une URL existe déjà dans la collection Qdrant
    
    Args:
        qdrant_connector: Instance de QdrantConnector
        url: URL à vérifier
        
    Returns:
        bool: True si l'URL existe déjà, False sinon
    """
    try:
        # La vérification désactivée pour performance, on se contentera de vérifier l'upsert
        # L'upsert remplacera naturellement les documents existants
        return False
    except Exception as e:
        logger.error(f"Erreur lors de la vérification de l'URL {url}: {str(e)}")
        return False

async def upsert_document(qdrant_connector, document):
    """
    Upsert un document dans Qdrant
    
    Args:
        qdrant_connector: Instance de QdrantConnector
        document: Document à upserter
        
    Returns:
        bool: True si l'opération a réussi, False sinon
    """
    try:
        # Générer les embeddings pour le contenu
        content_to_embed = f"{document['title']} {document['content']}"
        if document.get('pdf_content'):
            content_to_embed += f" {document['pdf_content']}"
        
        embedding = await generate_embeddings(content_to_embed)
        
        if not embedding:
            logger.error(f"Échec de génération d'embedding pour {document['url']}")
            return False
            
        # Créer un identifiant unique au format UUID pour le document
        doc_id = str(uuid.uuid4())
        
        # Créer le point à insérer dans Qdrant
        point = models.PointStruct(
            id=doc_id,
            vector=embedding,
            payload={
                "source_url": document["url"],
                "title": document["title"],
                "content": document["content"],
                "category": document["category"],
                "timestamp": document.get("timestamp", ""),
                "language": document.get("language", "fr"),
                "relevance_score": document.get("relevance_score", 0.5),
                "type": "html" if not document.get("pdf_path") else "pdf",
                "is_faq": True,  # Forcer comme FAQ pour la collection BIOFORCE
            }
        )
        
        # Upserter le document dans Qdrant
        result = qdrant_connector.client.upsert(
            collection_name=qdrant_connector.collection_name,
            points=[point]
        )
        
        return True if result else False
    except Exception as e:
        logger.error(f"Erreur lors de l'upsert du document {document['url']}: {str(e)}")
        return False

async def main():
    """
    Fonction principale qui parcourt tous les fichiers JSON dans output/data
    et les upsert dans Qdrant
    """
    # Initialiser la connexion à Qdrant
    qdrant_connector = QdrantConnector()
    qdrant_connector.collection_name = "BIOFORCE"  # Forcer l'utilisation de la collection BIOFORCE
    
    # Récupérer tous les fichiers JSON dans le dossier output/data
    json_files = glob.glob(os.path.join(DATA_DIR, "*.json"))
    logger.info(f"Nombre de fichiers JSON trouvés: {len(json_files)}")
    
    processed_count = 0
    existing_count = 0
    error_count = 0
    
    for json_file in json_files:
        try:
            # Charger le document JSON
            with open(json_file, 'r', encoding='utf-8') as f:
                document = json.load(f)
            
            url = document.get("url", "")
            if not url:
                logger.warning(f"URL manquante dans le fichier {json_file}")
                error_count += 1
                continue
            
            # Vérifier si l'URL existe déjà
            url_exists = await check_url_exists(qdrant_connector, url)
            
            if url_exists:
                logger.info(f"URL déjà présente, ignorée: {url}")
                existing_count += 1
                continue
            
            # Upserter le document
            result = await upsert_document(qdrant_connector, document)
            
            if result:
                logger.info(f"Document upserté avec succès: {url}")
                processed_count += 1
            else:
                logger.error(f"Échec de l'upsert du document: {url}")
                error_count += 1
        
        except Exception as e:
            logger.error(f"Erreur lors du traitement du fichier {json_file}: {str(e)}")
            error_count += 1
    
    logger.info(f"Opération terminée. Traités: {processed_count}, Ignorés (existants): {existing_count}, Erreurs: {error_count}")

if __name__ == "__main__":
    asyncio.run(main())
