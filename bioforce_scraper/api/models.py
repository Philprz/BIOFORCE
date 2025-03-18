"""
Module définissant les modèles de données pour l'API Bioforce.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Modèle pour les requêtes de recherche"""
    query: str = Field(..., description="Requête de recherche")
    collection: str = Field("faq", description="Collection à interroger (faq ou full)")
    limit: int = Field(5, description="Nombre maximum de résultats à retourner")


class ScrapeRequest(BaseModel):
    """Modèle pour les requêtes de scraping"""
    force_update: bool = Field(False, description="Forcer la mise à jour même si les données existent")


class Message(BaseModel):
    """Modèle pour un message dans une conversation"""
    role: str = Field(..., description="Rôle du message (user ou assistant)")
    content: str = Field(..., description="Contenu du message")


class ChatRequest(BaseModel):
    """Modèle pour les requêtes de chat"""
    user_id: str = Field("anonymous", description="Identifiant de l'utilisateur")
    messages: List[Message] = Field([], description="Historique des messages")
    context: Optional[Dict[str, Any]] = Field(None, description="Contexte additionnel pour la conversation")
