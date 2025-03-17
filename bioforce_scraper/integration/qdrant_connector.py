"""
Module d'intégration avec Qdrant pour stocker les données scrapées dans la base vectorielle
"""
import logging
import os
import time
from typing import Dict, List, Optional, Any

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse

from config import LOG_FILE
from utils.logger import setup_logger

logger = setup_logger(__name__, LOG_FILE)

class QdrantConnector:
    """
    Connector pour intégrer les données scrapées dans Qdrant
    """
    
    def __init__(self, url=None, api_key=None, collection_name="bioforce_knowledge"):
        """
        Initialise la connexion à Qdrant
        
        Args:
            url: URL du serveur Qdrant (si None, utilise l'environnement ou localhost)
            api_key: Clé API pour Qdrant (si None, utilise l'environnement)
            collection_name: Nom de la collection Qdrant
        """
        self.url = url or os.getenv("QDRANT_URL", "http://localhost:6333")
        self.api_key = api_key or os.getenv("QDRANT_API_KEY")
        self.collection_name = collection_name
        
        # Tenter de se connecter à Qdrant
        try:
            self.client = QdrantClient(url=self.url, api_key=self.api_key)
            logger.info(f"Connecté à Qdrant: {self.url}")
        except Exception as e:
            logger.error(f"Erreur de connexion à Qdrant: {e}")
            self.client = None
    
    def ensure_collection(self, vector_size=1536):
        """
        S'assure que la collection existe, la crée si ce n'est pas le cas
        
        Args:
            vector_size: Taille des vecteurs d'embedding
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
                    field_name="category",
                    field_schema=models.PayloadSchemaType.KEYWORD
                )
                
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="type",
                    field_schema=models.PayloadSchemaType.KEYWORD
                )
                
                logger.info(f"Collection '{self.collection_name}' créée avec succès")
            else:
                logger.info(f"Collection '{self.collection_name}' existe déjà")
            
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la création de la collection: {e}")
            return False
    
    def get_document_ids_by_url(self, url: str) -> List[str]:
        """
        Récupère les IDs des documents dans Qdrant ayant l'URL spécifiée
        
        Args:
            url: URL source du document
            
        Returns:
            Liste des IDs de points
        """
        if not self.client:
            logger.error("Client Qdrant non initialisé")
            return []
        
        try:
            # Rechercher par URL exacte
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
                limit=100,  # Limite max par précaution
                with_payload=True,
                with_vectors=False
            )
            
            # Extraire les IDs
            points = search_result[0]
            return [str(point.id) for point in points]
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche de documents par URL: {e}")
            return []
    
    def get_all_urls(self) -> List[str]:
        """
        Récupère toutes les URLs stockées dans Qdrant
        
        Returns:
            Liste des URLs uniques
        """
        if not self.client:
            logger.error("Client Qdrant non initialisé")
            return []
        
        try:
            # Récupérer tous les points avec uniquement le payload source_url
            urls = set()
            
            # Utiliser scroll pour parcourir tous les résultats
            offset = None
            while True:
                result = self.client.scroll(
                    collection_name=self.collection_name,
                    limit=1000,
                    offset=offset,
                    with_payload=["source_url"],
                    with_vectors=False
                )
                
                points, offset = result
                
                if not points:
                    break
                
                # Extraire les URLs uniques
                for point in points:
                    if point.payload and "source_url" in point.payload:
                        urls.add(point.payload["source_url"])
            
            return list(urls)
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des URLs: {e}")
            return []
    
    def _generate_dummy_embedding(self, size=1536):
        """
        Génère un embedding temporaire (à remplacer par un vrai embedding)
        
        Args:
            size: Taille du vecteur
            
        Returns:
            Vecteur normalisé
        """
        # Créer un vecteur aléatoire et le normaliser
        vector = np.random.rand(size)
        return vector / np.linalg.norm(vector)
    
    def upsert_document_chunks(self, document: Dict[str, Any], generate_id=True, chunk_size=1000):
        """
        Insère ou met à jour un document dans Qdrant, en le divisant en chunks
        
        Args:
            document: Document à insérer (avec l'URL source et le contenu)
            generate_id: Si True, génère des IDs basés sur l'URL et le numéro de chunk
            chunk_size: Taille maximale de chaque chunk en caractères
            
        Returns:
            True si l'opération a réussi, False sinon
        """
        if not self.client:
            logger.error("Client Qdrant non initialisé")
            return False
        
        if not document.get("content"):
            logger.warning("Document sans contenu, impossible à insérer")
            return False
        
        try:
            # S'assurer que la collection existe
            self.ensure_collection()
            
            # Vérifier si le document existe déjà
            source_url = document.get("source_url")
            existing_ids = self.get_document_ids_by_url(source_url)
            
            # Si le document existe, le supprimer d'abord
            if existing_ids:
                logger.info(f"Suppression de {len(existing_ids)} chunks existants pour {source_url}")
                self.client.delete(
                    collection_name=self.collection_name,
                    points_selector=models.PointIdsList(points=existing_ids)
                )
            
            # Diviser le contenu en chunks
            content = document.get("content", "")
            chunks = self._split_text_into_chunks(content, chunk_size)
            
            # Préparer les points à insérer
            points = []
            
            for i, chunk in enumerate(chunks):
                # Générer un ID basé sur l'URL et le numéro de chunk si demandé
                if generate_id:
                    import hashlib
                    # Créer un hash de l'URL + numéro de chunk pour un ID stable
                    id_str = f"{source_url}_{i}"
                    point_id = hashlib.md5(id_str.encode()).hexdigest()
                else:
                    # Sinon, utiliser un ID aléatoire
                    import uuid
                    point_id = str(uuid.uuid4())
                
                # À terme, il faudrait utiliser un vrai embedding ici
                # Pour l'instant, on utilise un vecteur aléatoire normalisé
                # qui sera remplacé par l'appel à une API d'embedding
                vector = self._generate_dummy_embedding()
                
                # Créer le payload
                payload = {
                    "source_url": source_url,
                    "title": document.get("title", ""),
                    "chunk_number": i,
                    "total_chunks": len(chunks),
                    "content": chunk,
                    "category": document.get("category", ""),
                    "type": document.get("type", ""),
                    "language": document.get("language", ""),
                    "date_extraction": document.get("date_extraction", ""),
                }
                
                # Ajouter les métadonnées si disponibles
                if "metadata" in document:
                    for key, value in document["metadata"].items():
                        # Éviter les conflits de noms
                        payload[f"metadata_{key}"] = value
                
                points.append(models.PointStruct(
                    id=point_id,
                    vector=vector.tolist(),
                    payload=payload
                ))
            
            # Insérer les points par lots de 100 maximum
            batch_size = 100
            for i in range(0, len(points), batch_size):
                batch = points[i:i+batch_size]
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=batch
                )
                logger.info(f"Inséré lot {i//batch_size + 1}/{(len(points) + batch_size - 1)//batch_size} pour {source_url}")
                # Pause pour éviter de surcharger l'API
                time.sleep(0.1)
            
            logger.info(f"Document inséré avec succès: {source_url} ({len(chunks)} chunks)")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de l'insertion du document: {e}")
            return False
    
    def _split_text_into_chunks(self, text: str, chunk_size: int) -> List[str]:
        """
        Divise un texte en chunks d'une taille maximale spécifiée
        
        Args:
            text: Texte à diviser
            chunk_size: Taille maximale de chaque chunk en caractères
            
        Returns:
            Liste de chunks
        """
        if not text:
            return []
        
        # Si le texte est plus petit que la taille du chunk, le retourner tel quel
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        current_pos = 0
        
        while current_pos < len(text):
            # Trouver la fin du chunk
            end_pos = min(current_pos + chunk_size, len(text))
            
            # Si nous ne sommes pas à la fin du texte, chercher la fin de phrase ou de paragraphe
            if end_pos < len(text):
                # Chercher la dernière fin de paragraphe
                last_para = text.rfind('\n\n', current_pos, end_pos)
                
                if last_para != -1 and last_para > current_pos + chunk_size // 2:
                    # Si on trouve une fin de paragraphe et qu'elle est suffisamment loin du début
                    end_pos = last_para + 2  # Inclure les deux retours à la ligne
                else:
                    # Sinon, chercher la dernière fin de phrase
                    for separator in ['. ', '! ', '? ', '.\n', '!\n', '?\n']:
                        last_sentence = text.rfind(separator, current_pos, end_pos)
                        if last_sentence != -1 and last_sentence > current_pos + chunk_size // 3:
                            end_pos = last_sentence + len(separator)
                            break
            
            # Extraire le chunk
            chunk = text[current_pos:end_pos].strip()
            if chunk:  # Ne pas ajouter de chunks vides
                chunks.append(chunk)
            
            # Passer au chunk suivant
            current_pos = end_pos
        
        return chunks
