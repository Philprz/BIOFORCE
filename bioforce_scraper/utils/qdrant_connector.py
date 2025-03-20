"""
Module de connexion à Qdrant pour stocker les embeddings
"""
import os
import logging
from typing import Dict, List, Optional, Any
from qdrant_client import QdrantClient, models
from bioforce_scraper.config import (
    QDRANT_COLLECTION, QDRANT_COLLECTION_ALL, VECTOR_SIZE
)

logger = logging.getLogger(__name__)

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
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Utilisation des variables d'environnement si non spécifiées
        self.url = url or os.getenv("QDRANT_URL") or os.getenv("QDRANT_HOST")
        self.api_key = api_key or os.getenv("QDRANT_API_KEY")
        
        # Détermine quelle collection utiliser
        if collection_name:
            self.collection_name = collection_name
        else:
            self.collection_name = QDRANT_COLLECTION_ALL if is_full_site else QDRANT_COLLECTION
        
        # Tenter de se connecter à Qdrant avec une approche simple
        try:
            self.client = QdrantClient(url=self.url, api_key=self.api_key)
            self.logger.info(f"Connecté à Qdrant: {self.url}, collection: {self.collection_name}")
        except Exception as e:
            self.logger.error(f"Erreur de connexion à Qdrant: {e}")
            self.client = None
    
    def _test_connection(self):
        """Test simple de connexion à Qdrant"""
        if not self.client:
            self.logger.error("Impossible de tester la connexion: client non initialisé")
            return False
            
        try:
            self.client.get_collections()
            return True
        except Exception as e:
            self.logger.error(f"Erreur de connexion à Qdrant: {e}")
            return False
    
    def ensure_collection(self, vector_size: int = VECTOR_SIZE) -> bool:
        """
        S'assure que la collection existe, la crée si ce n'est pas le cas
        
        Args:
            vector_size: Taille des vecteurs d'embedding
            
        Returns:
            True si la collection existe ou a été créée, False sinon
        """
        if not self.client:
            logger.error("Client Qdrant non initialisé")
            return False
        
        try:
            # Vérifier si la collection existe
            collections = self.client.get_collections().collections
            collection_names = [collection.name for collection in collections]
            
            if self.collection_name not in collection_names:
                # Créer la collection
                logger.info(f"Création de la collection {self.collection_name}...")
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=vector_size,
                        distance=models.Distance.COSINE
                    )
                )
                
                # Créer les index pour la recherche par payload
                try:
                    self.client.create_payload_index(
                        collection_name=self.collection_name,
                        field_name="source_url",
                        field_schema=models.PayloadSchemaType.KEYWORD
                    )
                    
                    # Ajouter d'autres index utiles pour le filtrage
                    self.client.create_payload_index(
                        collection_name=self.collection_name,
                        field_name="language",
                        field_schema=models.PayloadSchemaType.KEYWORD
                    )
                    
                    self.client.create_payload_index(
                        collection_name=self.collection_name,
                        field_name="category",
                        field_schema=models.PayloadSchemaType.KEYWORD
                    )
                    
                    logger.info(f"Collection {self.collection_name} créée avec succès")
                except Exception as e:
                    logger.warning(f"Erreur lors de la création des index pour {self.collection_name}: {str(e)}")
                    # Ne pas échouer complètement si les index ne peuvent pas être créés
                
                return True
            else:
                logger.info(f"Collection {self.collection_name} existe déjà")
                return True
                
        except Exception as e:
            logger.error(f"Erreur lors de la vérification/création de la collection {self.collection_name}: {str(e)}")
            return False
    
    def search(self, query_vector: List[float], limit: int = 5, 
              filter_conditions: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Recherche les documents les plus similaires au vecteur de requête
        
        Args:
            query_vector: Vecteur d'embedding de la requête
            limit: Nombre maximum de résultats
            filter_conditions: Conditions de filtrage (par exemple, par type de document)
            
        Returns:
            Liste des documents trouvés avec leurs scores de similarité
        """
        if not self.client:
            self.logger.error("Client Qdrant non disponible")
            return []
        
        try:
            # Préparer les filtres s'ils existent
            search_filter = None
            if filter_conditions:
                filter_must = []
                
                for field, value in filter_conditions.items():
                    if isinstance(value, list):
                        # Pour les listes (OR)
                        should = []
                        for v in value:
                            should.append(models.FieldCondition(
                                key=field,
                                match=models.MatchValue(value=v)
                            ))
                        filter_must.append(models.Filter(should=should))
                    else:
                        # Pour les valeurs simples (AND)
                        filter_must.append(models.FieldCondition(
                            key=field,
                            match=models.MatchValue(value=value)
                        ))
                
                search_filter = models.Filter(must=filter_must)
            
            # On récupère un peu plus de résultats pour pouvoir filtrer par score ensuite
            search_limit = max(20, limit * 2)
            
            # Effectuer la recherche
            search_result = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=search_limit,
                query_filter=search_filter,
                with_payload=True,
                with_vectors=False
            )
            
            # Formater les résultats et filtrer par score
            results = []
            min_score_threshold = 0.001  # Seuil minimal de score
            
            for scoring_point in search_result:
                if scoring_point.score >= min_score_threshold:
                    results.append({
                        "id": scoring_point.id,
                        "score": scoring_point.score,
                        "payload": scoring_point.payload
                    })
            
            # Trier par score et limiter aux "limit" premiers résultats
            results = sorted(results, key=lambda x: x["score"], reverse=True)[:limit]
            
            return results
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la recherche: {e}")
            return []
    
    def upsert_document(self, id: str, vector: List[float], payload: Dict[str, Any]) -> bool:
        """
        Insère ou met à jour un document dans Qdrant
        
        Args:
            id: Identifiant unique du document
            vector: Vecteur d'embedding
            payload: Métadonnées du document
            
        Returns:
            True si l'opération a réussi, False sinon
        """
        if not self.client:
            logger.error("Client Qdrant non initialisé")
            return False
        
        try:
            # S'assurer que la collection existe
            self.ensure_collection()
            
            # Insérer ou mettre à jour le document
            self.client.upsert(
                collection_name=self.collection_name,
                points=[
                    models.PointStruct(
                        id=id,
                        vector=vector,
                        payload=payload
                    )
                ]
            )
            
            logger.info(f"Document inséré/mis à jour avec succès: ID={id}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de l'insertion/mise à jour du document: {e}")
            return False
    
    def delete_document(self, id: str) -> bool:
        """
        Supprime un document de Qdrant
        
        Args:
            id: Identifiant unique du document
            
        Returns:
            True si l'opération a réussi, False sinon
        """
        if not self.client:
            logger.error("Client Qdrant non initialisé")
            return False
        
        try:
            # Supprimer le document
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.PointIdsList(
                    points=[id]
                )
            )
            
            logger.info(f"Document supprimé avec succès: ID={id}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la suppression du document: {e}")
            return False
    
    def upsert_document_chunks(self, payload: Dict[str, Any], generate_id: bool = False) -> bool:
        """
        Insère ou met à jour un document dans Qdrant via des chunks.
        Force la création du doc_id en utilisant un UUID en hexadécimal.

        Args:
            payload (Dict[str, Any]): Données à indexer contenant "source_url", "title", "content", etc.
            generate_id (bool): Ce paramètre est ignoré car le doc_id est toujours généré.

        Returns:
            bool: True si l'opération a réussi, False sinon.
        """
        from uuid import uuid4

        # Forcer la création d'un identifiant en UUID (hexadécimal de 32 caractères)
        doc_id = uuid4().hex

        vector = payload.get("vector")
        return self.upsert_document(doc_id, vector, payload)
    
    def get_document_by_url(self, url: str) -> List[Dict]:
        """
        Récupère les documents associés à une URL
        
        Args:
            url: URL source du document
            
        Returns:
            Liste des documents trouvés
        """
        if not self.client:
            logger.error("Client Qdrant non initialisé")
            return []
        
        try:
            # Rechercher par URL
            search_result = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="source_url",
                            match=models.MatchValue(value=url)
                        )
                    ]
                ),
                limit=100,
                with_payload=True,
                with_vectors=False
            )
            
            points, _ = search_result
            
            # Formater les résultats
            results = []
            for point in points:
                results.append({
                    "id": point.id,
                    "payload": point.payload
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des documents par URL: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Récupère des statistiques sur la collection
        
        Returns:
            Dictionnaire contenant les statistiques
        """
        if not self.client:
            logger.error("Client Qdrant non initialisé")
            return {}
        
        try:
            # Récupérer les statistiques de la collection
            collection_info = self.client.get_collection(self.collection_name)
            
            # Calculer les statistiques par type de document
            stats_by_type = {}
            
            try:
                # Récupérer les types uniques
                scroll_result = self.client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=None,
                    limit=10000,
                    with_payload=["type"],
                    with_vectors=False
                )
                
                points, _ = scroll_result
                
                # Compter les occurrences de chaque type
                for point in points:
                    doc_type = point.payload.get("type", "unknown")
                    if doc_type not in stats_by_type:
                        stats_by_type[doc_type] = 0
                    stats_by_type[doc_type] += 1
                    
            except Exception as e:
                logger.error(f"Erreur lors du calcul des statistiques par type: {e}")
            
            return {
                "points_count": collection_info.points_count,
                "vectors_count": collection_info.vectors_count,
                "indexed_vectors_count": collection_info.indexed_vectors_count,
                "by_type": stats_by_type
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des statistiques: {e}")
            return {}
