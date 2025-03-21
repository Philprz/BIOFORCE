"""
Connecteur pour Qdrant, gestionnaire de vecteurs pour la recherche
"""
import os
import logging
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv

from qdrant_client import AsyncQdrantClient
from qdrant_client import models

# Import de la configuration
from bioforce_scraper.config import VECTOR_SIZE, QDRANT_COLLECTION, QDRANT_COLLECTION_ALL

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Chargement des variables d'environnement
load_dotenv()

class QdrantConnector:
    """
    Classe pour interagir avec Qdrant
    """
    
    def __init__(self, url: Optional[str] = None, api_key: Optional[str] = None, 
                collection_name: Optional[str] = None, is_full_site: bool = False):
        """
        Initialise la connexion à Qdrant
        
        Args:
            url: URL du serveur Qdrant (utilisera QDRANT_URL de config.py si None)
            api_key: Clé API pour Qdrant (utilisera QDRANT_API_KEY de config.py si None)
            collection_name: Nom de la collection (utilisera QDRANT_COLLECTION de config.py si None)
            is_full_site: Si True, utilise la collection pour le site complet (QDRANT_COLLECTION_ALL)
        """
        try:
            self.url = url or os.getenv("QDRANT_URL")
            self.api_key = api_key or os.getenv("QDRANT_API_KEY")
            
            # Détermine quelle collection utiliser
            if collection_name:
                self.collection_name = collection_name
            else:
                self.collection_name = os.getenv("QDRANT_COLLECTION_ALL", QDRANT_COLLECTION_ALL) if is_full_site else os.getenv("QDRANT_COLLECTION", QDRANT_COLLECTION)
            
            logger.info(f"URL Qdrant: {self.url}")
            logger.info(f"API Key Qdrant: {self.api_key[:10]}... (tronquée pour sécurité)")
            logger.info(f"Collection Qdrant: {self.collection_name}")
            
            if not self.url:
                raise ValueError("URL Qdrant non configurée. Définissez QDRANT_URL dans le fichier .env")
            
            if not self.api_key:
                raise ValueError("API Key Qdrant non configurée. Définissez QDRANT_API_KEY dans le fichier .env")
            
            # Initialisation avec la nouvelle version de qdrant-client
            self.client = AsyncQdrantClient(url=self.url, api_key=self.api_key, timeout=30)
            logger.info(f"Connexion à Qdrant initialisée: {self.url}, collection: {self.collection_name}")
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation de la connexion Qdrant: {str(e)}")
            # On relève l'exception pour ne pas masquer l'erreur
            raise
    
    async def ensure_collection(self, vector_size: int = VECTOR_SIZE) -> bool:
        """
        S'assure que la collection existe et crée celle-ci si nécessaire
        """
        try:
            # Vérifier si la collection existe
            collections = await self.client.get_collections()
            collection_names = [collection.name for collection in collections.collections]
            
            if self.collection_name in collection_names:
                # La collection existe déjà
                # Récupérer le nombre de points pour le log
                count = await self.client.count(collection_name=self.collection_name)
                logger.info(f"Collection {self.collection_name} trouvée avec {count.count} points")
                return True
            
            # La collection n'existe pas, on la crée
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE
                )
            )
            logger.info(f"Collection {self.collection_name} créée avec succès")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification/création de la collection {self.collection_name}: {str(e)}")
            return False
    
    async def search(self, query_vector: List[float], limit: int = 5, 
               filter_conditions: Optional[Dict] = None) -> List[Dict]:
        """
        Effectue une recherche par similarité dans Qdrant
        """
        try:
            if filter_conditions is None:
                search_result = await self.client.search(
                    collection_name=self.collection_name,
                    query_vector=query_vector,
                    limit=limit
                )
            else:
                search_result = await self.client.search(
                    collection_name=self.collection_name,
                    query_vector=query_vector,
                    limit=limit,
                    query_filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key=key,
                                match=models.MatchValue(value=value)
                            ) for key, value in filter_conditions.items()
                        ]
                    )
                )
            
            # Convertir les résultats en dictionnaires
            results = []
            for scored_point in search_result:
                point_dict = {
                    "id": scored_point.id,
                    "score": scored_point.score,
                    "payload": scored_point.payload
                }
                results.append(point_dict)
            
            return results
        
        except Exception as e:
            logger.error(f"Erreur lors de la recherche dans Qdrant: {str(e)}")
            return []
    
    async def upsert_document(self, id: str, vector: List[float], payload: Dict[str, Any]) -> bool:
        """
        Ajoute ou met à jour un document dans Qdrant
        """
        try:
            await self.client.upsert(
                collection_name=self.collection_name,
                points=[
                    models.PointStruct(
                        id=id,
                        vector=vector,
                        payload=payload
                    )
                ]
            )
            logger.debug(f"Document {id} ajouté/mis à jour avec succès")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de l'ajout/mise à jour du document {id}: {str(e)}")
            return False
    
    async def delete_document(self, id: str) -> bool:
        """
        Supprime un document de Qdrant
        """
        try:
            await self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.PointIdsList(
                    points=[id]
                )
            )
            logger.debug(f"Document {id} supprimé avec succès")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la suppression du document {id}: {str(e)}")
            return False
    
    async def get_document_by_url(self, url: str) -> List[Dict]:
        """
        Récupère un document par son URL
        """
        try:
            # Recherche par URL dans le payload
            result = await self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="source_url",
                            match=models.MatchValue(value=url)
                        )
                    ]
                ),
                limit=10  # Limite à 10 documents au cas où il y aurait des doublons
            )
            
            if not result.points:
                return []
                
            # Convertir les résultats
            documents = []
            for point in result.points:
                documents.append({
                    "id": point.id,
                    "payload": point.payload
                })
                
            return documents
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche du document par URL {url}: {str(e)}")
            return []
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Récupère les statistiques de la collection
        """
        try:
            # Vérifier que la collection existe
            collections = await self.client.get_collections()
            collection_names = [collection.name for collection in collections.collections]
            
            if self.collection_name not in collection_names:
                return {
                    "status": "error",
                    "message": f"Collection {self.collection_name} non trouvée",
                    "collection_exists": False,
                    "count": 0
                }
                
            # Récupérer les informations de la collection
            count = await self.client.count(collection_name=self.collection_name)
            
            # Récupérer une répartition par type de document
            types_stats = {}
            categories_stats = {}
            
            return {
                "status": "success",
                "collection_exists": True,
                "count": count.count,
                "types": types_stats,
                "categories": categories_stats
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des statistiques: {str(e)}")
            return {
                "status": "error", 
                "message": str(e),
                "collection_exists": False,
                "count": 0
            }
