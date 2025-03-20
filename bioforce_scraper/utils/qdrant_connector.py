"""
Module de connexion à Qdrant pour stocker les embeddings
"""
import logging
import os
from typing import Dict, List, Any, Optional, Union

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse

from bioforce_scraper.config import (QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION, QDRANT_COLLECTION_ALL, 
                   VECTOR_SIZE, LOG_FILE)
from bioforce_scraper.utils.logger import setup_logger

# Configuration du logger
logger = setup_logger(__name__, LOG_FILE)

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
        self.url = url or QDRANT_URL
        self.api_key = api_key or QDRANT_API_KEY
        
        # Détermine quelle collection utiliser
        if collection_name:
            self.collection_name = collection_name
        else:
            self.collection_name = QDRANT_COLLECTION_ALL if is_full_site else QDRANT_COLLECTION
        
        # Tenter de se connecter à Qdrant
        try:
            self.client = QdrantClient(url=self.url, api_key=self.api_key)
            logger.info(f"Connecté à Qdrant: {self.url}, collection: {self.collection_name}")
        except Exception as e:
            logger.error(f"Erreur de connexion à Qdrant: {e}")
            self.client = None
    
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
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=vector_size,
                        distance=models.Distance.COSINE
                    )
                )
                
                # Créer les index pour la recherche par payload
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="source_url",
                    field_schema=models.PayloadSchemaType.KEYWORD
                )
                
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="type",
                    field_schema=models.PayloadSchemaType.KEYWORD
                )
                
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="category",
                    field_schema=models.PayloadSchemaType.KEYWORD
                )
                
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="language",
                    field_schema=models.PayloadSchemaType.KEYWORD
                )
                
                logger.info(f"Collection '{self.collection_name}' créée avec succès")
            else:
                logger.info(f"Collection '{self.collection_name}' existe déjà")
            
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la création de la collection: {e}")
            return False
    
    def search(self, query_vector: List[float], limit: int = 5, 
              filter_conditions: Optional[Dict] = None) -> List[Dict]:
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
            logger.error("Client Qdrant non initialisé")
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
            
            # Effectuer la recherche
            search_result = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit,
                query_filter=search_filter,
                with_payload=True,
                with_vectors=False
            )
            
            # Formater les résultats
            results = []
            for scoring_point in search_result:
                results.append({
                    "id": scoring_point.id,
                    "score": scoring_point.score,
                    "payload": scoring_point.payload
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche: {e}")
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
