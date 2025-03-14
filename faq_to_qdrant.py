import os
import json
import uuid
import logging
import asyncio
import hashlib
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

# Configurer le logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Charger les variables d'environnement
load_dotenv()

# Configuration
INPUT_FILE = "Faq_20250313_165055.json"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION")
BATCH_SIZE = 20
EMBEDDING_MODEL = "text-embedding-3-small"
VECTOR_SIZE = 1536

def generate_content_hash(question, reponse):
    """Génère un hash unique basé sur le contenu de la question et la réponse"""
    content = f"{question}|{reponse}".lower().strip()
    return hashlib.md5(content.encode('utf-8')).hexdigest()

async def generate_embedding(openai_client, text):
    """Génère un embedding pour le texte donné"""
    try:
        response = await openai_client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Erreur lors de la génération de l'embedding: {e}")
        raise

async def ensure_collection_exists(qdrant_client):
    """S'assure que la collection existe, sinon la crée"""
    try:
        collections = await qdrant_client.get_collections()
        collection_names = [c.name for c in collections.collections]
        
        if QDRANT_COLLECTION not in collection_names:
            logger.info(f"Création de la collection {QDRANT_COLLECTION}")
            # Créer d'abord la collection avec les configurations de base
            await qdrant_client.create_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config=models.VectorParams(
                    size=VECTOR_SIZE,
                    distance=models.Distance.COSINE
                ),
                optimizers_config=models.OptimizersConfigDiff(
                    indexing_threshold=0
                )
            )
            
            # Puis ajouter l'index pour content_hash
            logger.info("Ajout de l'index content_hash")
            await qdrant_client.create_payload_index(
                collection_name=QDRANT_COLLECTION,
                field_name="content_hash",
                field_schema=models.PayloadSchemaType.KEYWORD
            )
            
            logger.info(f"Collection {QDRANT_COLLECTION} créée avec succès")
        else:
            logger.info(f"La collection {QDRANT_COLLECTION} existe déjà")
            # Vérifier si l'index content_hash existe, sinon le créer
            try:
                collection_info = await qdrant_client.get_collection(collection_name=QDRANT_COLLECTION)
                payload_indexes = collection_info.payload_schema
                
                # Si payload_schema est None ou content_hash n'existe pas dans les index
                if payload_indexes is None or "content_hash" not in payload_indexes:
                    logger.info("Ajout de l'index content_hash à la collection existante")
                    await qdrant_client.create_payload_index(
                        collection_name=QDRANT_COLLECTION,
                        field_name="content_hash",
                        field_schema=models.PayloadSchemaType.KEYWORD
                    )
            except Exception as e:
                logger.warning(f"Impossible de vérifier les index existants: {e}")
                # En cas d'erreur, on tente d'ajouter l'index quand même
                try:
                    await qdrant_client.create_payload_index(
                        collection_name=QDRANT_COLLECTION,
                        field_name="content_hash",
                        field_schema=models.PayloadSchemaType.KEYWORD
                    )
                except Exception as e2:
                    logger.warning(f"Impossible d'ajouter l'index content_hash: {e2}")
                    # On continue quand même, car ce n'est pas bloquant
                    pass
    except Exception as e:
        logger.error(f"Erreur lors de la vérification/création de la collection: {e}")
        raise

async def check_if_exists(qdrant_client, content_hash):
    """Vérifie si une entrée avec ce hash existe déjà dans la collection"""
    try:
        search_result = await qdrant_client.scroll(
            collection_name=QDRANT_COLLECTION,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="content_hash",
                        match=models.MatchValue(value=content_hash)
                    )
                ]
            ),
            limit=1
        )
        
        # Si des résultats sont trouvés, l'entrée existe déjà
        return len(search_result[0]) > 0
    except Exception as e:
        logger.error(f"Erreur lors de la vérification d'existence: {e}")
        # En cas d'erreur, on suppose que l'entrée n'existe pas
        return False

async def load_faq_data(file_path):
    """Charge les données FAQ depuis le fichier JSON"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info(f"Données FAQ chargées depuis {file_path}: {len(data)} entrées trouvées")
        return data
    except Exception as e:
        logger.error(f"Erreur lors du chargement des données FAQ: {e}")
        raise

async def cleanup_duplicates(qdrant_client):
    """Nettoie les entrées dupliquées existantes dans la collection"""
    try:
        # Cette fonction est complexe et pourrait être implémentée différemment
        # selon les besoins exacts, mais voici une approche basique
        
        logger.info("Vérification des doublons existants...")
        
        # Récupérer toutes les entrées
        all_points = []
        offset = 0
        limit = 100
        
        while True:
            result = await qdrant_client.scroll(
                collection_name=QDRANT_COLLECTION,
                limit=limit,
                offset=offset
            )
            
            points, next_page_offset = result
            
            if not points:
                break
                
            all_points.extend(points)
            
            if next_page_offset is None:
                break
                
            offset = next_page_offset
        
        logger.info(f"Total de {len(all_points)} points récupérés.")
        
        # Identifier les doublons basés sur le contenu
        seen_hashes = {}
        duplicates = []
        
        for point in all_points:
            # Générer un hash du contenu si ce n'est pas déjà présent
            if "content_hash" not in point.payload:
                content = f"{point.payload.get('question', '')}|{point.payload.get('reponse', '')}".lower().strip()
                content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
            else:
                content_hash = point.payload["content_hash"]
            
            if content_hash in seen_hashes:
                # C'est un doublon
                duplicates.append(point.id)
            else:
                seen_hashes[content_hash] = point.id
        
        # Supprimer les doublons
        if duplicates:
            logger.info(f"Suppression de {len(duplicates)} doublons identifiés...")
            
            # Supprimer par lots de 100
            for i in range(0, len(duplicates), 100):
                batch = duplicates[i:i+100]
                await qdrant_client.delete(
                    collection_name=QDRANT_COLLECTION,
                    points_selector=models.PointIdsList(
                        points=batch
                    )
                )
            
            logger.info("Nettoyage des doublons terminé.")
        else:
            logger.info("Aucun doublon trouvé.")
            
    except Exception as e:
        logger.error(f"Erreur lors du nettoyage des doublons: {e}")
        raise

async def main():
    """Fonction principale"""
    try:
        # Initialiser les clients
        logger.info("Initialisation des clients OpenAI et Qdrant...")
        openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        qdrant_client = AsyncQdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        
        # S'assurer que la collection existe
        await ensure_collection_exists(qdrant_client)
        
        # Option: nettoyer les doublons existants
        clean_existing = input("Voulez-vous nettoyer les doublons existants dans la collection ? (o/n): ").lower() == 'o'
        if clean_existing:
            await cleanup_duplicates(qdrant_client)
        
        # Charger les données FAQ
        faq_data = await load_faq_data(INPUT_FILE)
        
        # Préparer et insérer les données par lots
        total = len(faq_data)
        processed = 0
        inserted = 0
        skipped = 0
        batch = []
        
        logger.info(f"Début du traitement de {total} entrées FAQ...")
        
        for item in faq_data:
            # Générer un hash de contenu unique
            content_hash = generate_content_hash(item['Question'], item['Réponse'])
            
            # Vérifier si cet élément existe déjà
            exists = await check_if_exists(qdrant_client, content_hash)
            
            if exists:
                skipped += 1
                processed += 1
                logger.debug(f"Entrée ignorée (déjà existante): {item['Question'][:50]}...")
                continue
            
            # Construire le texte pour l'embedding
            text = f"Question: {item['Question']} Réponse: {item['Réponse']}"
            
            # Générer l'embedding
            embedding = await generate_embedding(openai_client, text)
            
            # Créer un ID unique
            point_id = str(uuid.uuid4())
            
            # Créer le point Qdrant
            point = models.PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "categorie": item['Catégorie'],
                    "titre": item['Titre'],
                    "question": item['Question'],
                    "reponse": item['Réponse'],
                    "content_hash": content_hash,  # Stocke le hash pour référence future
                    "source": "FAQ Bioforce",
                    "date_import": datetime.now().isoformat()
                }
            )
            
            batch.append(point)
            processed += 1
            inserted += 1
            
            # Insérer le lot quand il atteint la taille maximale
            if len(batch) >= BATCH_SIZE:
                logger.info(f"Insertion d'un lot de {len(batch)} points... ({processed}/{total})")
                await qdrant_client.upsert(
                    collection_name=QDRANT_COLLECTION,
                    points=batch
                )
                batch = []
            
            # Afficher la progression
            if processed % 20 == 0:
                logger.info(f"Progression: {processed}/{total} ({processed/total*100:.2f}%) - Insérés: {inserted}, Ignorés: {skipped}")
        
        # Insérer le dernier lot s'il existe
        if batch:
            logger.info(f"Insertion du dernier lot de {len(batch)} points...")
            await qdrant_client.upsert(
                collection_name=QDRANT_COLLECTION,
                points=batch
            )
        
        logger.info(f"Importation terminée. {processed} entrées traitées: {inserted} importées, {skipped} ignorées car déjà existantes.")
        
        # Fermer le client Qdrant
        await qdrant_client.close()
        
    except Exception as e:
        logger.error(f"Erreur lors de l'exécution du script: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())
