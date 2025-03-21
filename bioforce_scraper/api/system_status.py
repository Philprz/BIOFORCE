"""
Module pour gérer l'état du système Bioforce
Fournit une API pour vérifier l'état des services (OpenAI, Qdrant)
"""
import os
import asyncio
import logging
from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime

from dotenv import load_dotenv
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient

# Chargement des variables d'environnement
load_dotenv()

# Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
QDRANT_URL = os.getenv('QDRANT_URL')
QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')
QDRANT_COLLECTION = os.getenv('QDRANT_COLLECTION', 'BIOFORCE')
VECTOR_SIZE = int(os.getenv('VECTOR_SIZE', 1536))

# Configuration du logger
logger = logging.getLogger(__name__)

class SystemStatus(Enum):
    """Statuts possibles du système"""
    GREEN = "green"      # Tout fonctionne
    ORANGE = "orange"    # Problèmes mineurs / connexions partielles
    RED = "red"          # Pas de connexion
    UNKNOWN = "unknown"  # État inconnu

class ServiceStatus:
    """Statut d'un service"""
    def __init__(self, name: str):
        self.name = name
        self.status = SystemStatus.UNKNOWN
        self.message = "Non vérifié"
        self.details = {}
        self.last_checked = None
    
    def set_status(self, status: SystemStatus, message: str, details: Optional[Dict] = None):
        """Définit le statut du service"""
        self.status = status
        self.message = message
        self.details = details or {}
        self.last_checked = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit l'état en dictionnaire"""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "last_checked": self.last_checked.isoformat() if self.last_checked else None
        }

class SystemStatusManager:
    """Gestionnaire de l'état du système"""
    def __init__(self):
        self.services = {
            "openai": ServiceStatus("OpenAI"),
            "qdrant": ServiceStatus("Qdrant")
        }
        self.overall_status = SystemStatus.UNKNOWN
    
    def get_overall_status(self) -> SystemStatus:
        """Détermine l'état global du système basé sur l'état de chaque service"""
        statuses = [service.status for service in self.services.values()]
        
        if SystemStatus.RED in statuses:
            return SystemStatus.RED
        elif SystemStatus.ORANGE in statuses:
            return SystemStatus.ORANGE
        elif all(status == SystemStatus.GREEN for status in statuses):
            return SystemStatus.GREEN
        else:
            return SystemStatus.UNKNOWN
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit l'état du système en dictionnaire"""
        self.overall_status = self.get_overall_status()
        
        return {
            "overall_status": self.overall_status.value,
            "services": {name: service.to_dict() for name, service in self.services.items()},
            "timestamp": datetime.now().isoformat()
        }
    
    async def check_openai(self) -> None:
        """Vérifie la connexion à OpenAI"""
        service = self.services["openai"]
        
        if not OPENAI_API_KEY:
            service.set_status(
                SystemStatus.RED,
                "Clé API OpenAI non configurée",
                {"api_key_configured": False}
            )
            return
        
        try:
            # Initialiser le client OpenAI
            client = AsyncOpenAI(api_key=OPENAI_API_KEY)
            
            # Test simple d'embeddings
            response = await client.embeddings.create(
                input="Test de connexion Bioforce",
                model="text-embedding-ada-002"
            )
            
            # Vérification de la réponse
            if response.data and len(response.data) > 0 and len(response.data[0].embedding) > 0:
                embedding_size = len(response.data[0].embedding)
                service.set_status(
                    SystemStatus.GREEN,
                    f"Connexion OpenAI opérationnelle (taille embedding: {embedding_size})",
                    {"embedding_size": embedding_size}
                )
            else:
                service.set_status(
                    SystemStatus.ORANGE,
                    "Réponse OpenAI invalide",
                    {"response": str(response)}
                )
                
        except Exception as e:
            logger.error(f"Erreur lors de la vérification de OpenAI: {e}")
            service.set_status(
                SystemStatus.RED,
                f"Erreur de connexion OpenAI: {str(e)}",
                {"error_type": type(e).__name__}
            )
    
    async def check_qdrant(self) -> None:
        """Vérifie la connexion à Qdrant"""
        service = self.services["qdrant"]
        
        if not QDRANT_URL or not QDRANT_API_KEY:
            service.set_status(
                SystemStatus.RED,
                "Configuration Qdrant incomplète",
                {"url_configured": bool(QDRANT_URL), "api_key_configured": bool(QDRANT_API_KEY)}
            )
            return
        
        try:
            # Initialiser le client Qdrant
            client = AsyncQdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
            
            # Vérifier que Qdrant répond
            collections = await client.get_collections()
            collection_names = [c.name for c in collections.collections]
            
            # Vérifier si la collection existe
            if QDRANT_COLLECTION in collection_names:
                collection_info = await client.get_collection(collection_name=QDRANT_COLLECTION)
                count = await client.count(collection_name=QDRANT_COLLECTION)
                
                # Faire une recherche simple pour vérifier la fonctionnalité complète
                test_vector = [0.0] * VECTOR_SIZE
                search_result = await client.search(
                    collection_name=QDRANT_COLLECTION,
                    query_vector=test_vector,
                    limit=1
                )
                
                service.set_status(
                    SystemStatus.GREEN,
                    f"Connexion Qdrant opérationnelle ({count.count} points)",
                    {
                        "collections": collection_names,
                        "collection_info": {
                            "vectors_count": collection_info.vectors_count if hasattr(collection_info, 'vectors_count') else "N/A",
                            "points_count": count.count
                        },
                        "search_test": len(search_result) > 0
                    }
                )
            else:
                service.set_status(
                    SystemStatus.ORANGE,
                    f"Collection {QDRANT_COLLECTION} non trouvée",
                    {"available_collections": collection_names}
                )
                
        except Exception as e:
            logger.error(f"Erreur lors de la vérification de Qdrant: {e}")
            service.set_status(
                SystemStatus.RED,
                f"Erreur de connexion Qdrant: {str(e)}",
                {"error_type": type(e).__name__}
            )
    
    async def check_all(self) -> Dict[str, Any]:
        """Vérifie l'état de tous les services"""
        # Exécuter les vérifications en parallèle
        await asyncio.gather(
            self.check_openai(),
            self.check_qdrant()
        )
        
        return self.to_dict()

# Instance globale
status_manager = SystemStatusManager()

async def get_system_status() -> Dict[str, Any]:
    """Récupère l'état actuel du système"""
    return await status_manager.check_all()

# Fonctions auxiliaires pour le frontend
def get_status_color(status: str) -> str:
    """Récupère la couleur CSS correspondant au statut"""
    colors = {
        "green": "#2ecc71",  # Vert
        "orange": "#f39c12", # Orange
        "red": "#e74c3c",    # Rouge
        "unknown": "#95a5a6" # Gris
    }
    return colors.get(status, colors["unknown"])

def get_status_icon(status: str) -> str:
    """Récupère l'icône correspondant au statut"""
    icons = {
        "green": "✅",  # Coche verte
        "orange": "⚠️", # Avertissement
        "red": "❌",    # Croix rouge
        "unknown": "❓"  # Point d'interrogation
    }
    return icons.get(status, icons["unknown"])

def generate_status_html(status_data: Dict[str, Any]) -> str:
    """Génère le HTML pour afficher l'état du système"""
    overall_status = status_data["overall_status"]
    overall_color = get_status_color(overall_status)
    
    html = f"""
    <div class="system-status-widget">
        <div class="status-header">
            <h3>État du système</h3>
            <div class="status-indicator" style="background-color: {overall_color};">
                <div class="status-dot"></div>
            </div>
        </div>
        
        <div class="status-details">
    """
    
    # Ajouter chaque service
    for name, service in status_data["services"].items():
        service_color = get_status_color(service["status"])
        service_icon = get_status_icon(service["status"])
        
        html += f"""
        <div class="service-item">
            <div class="service-name">{service["name"]}</div>
            <div class="service-status" style="color: {service_color};">{service_icon} {service["status"].upper()}</div>
            <div class="service-message">{service["message"]}</div>
        </div>
        """
    
    html += """
        </div>
        <div class="status-footer">
            <small>Dernière vérification: <span class="timestamp"></span></small>
            <script>
                document.querySelector('.timestamp').textContent = new Date().toLocaleString();
                
                // Mettre à jour l'indicateur de statut (animation)
                setInterval(function() {
                    const dot = document.querySelector('.status-dot');
                    dot.classList.toggle('pulse');
                }, 1500);
            </script>
        </div>
    </div>
    
    <style>
        .system-status-widget {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
            padding: 15px;
            max-width: 400px;
            margin: 20px auto;
        }
        
        .status-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            border-bottom: 1px solid #eee;
            padding-bottom: 10px;
        }
        
        .status-header h3 {
            margin: 0;
            color: #333;
        }
        
        .status-indicator {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .status-dot {
            width: 20px;
            height: 20px;
            border-radius: 50%;
            background-color: white;
            transition: all 0.3s ease;
        }
        
        .status-dot.pulse {
            transform: scale(0.8);
            opacity: 0.8;
        }
        
        .service-item {
            margin-bottom: 12px;
            padding-bottom: 12px;
            border-bottom: 1px solid #f5f5f5;
        }
        
        .service-name {
            font-weight: bold;
            margin-bottom: 5px;
        }
        
        .service-status {
            font-size: 0.9em;
            font-weight: bold;
            margin-bottom: 5px;
        }
        
        .service-message {
            font-size: 0.85em;
            color: #666;
        }
        
        .status-footer {
            margin-top: 15px;
            text-align: center;
            color: #999;
            font-size: 0.8em;
        }
    </style>
    """
    
    return html
