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
            logger.error("Vérification OpenAI: Clé API non configurée")
            return
        
        try:
            logger.info("Démarrage de la vérification OpenAI...")
            
            # Initialiser le client OpenAI
            logger.debug(f"Initialisation du client OpenAI avec la clé API: {OPENAI_API_KEY[:5]}...")
            client = AsyncOpenAI(api_key=OPENAI_API_KEY)
            
            # Test simple d'embeddings
            logger.debug("Test d'embedding avec OpenAI...")
            start_time = datetime.now()
            response = await client.embeddings.create(
                input="Test de connexion Bioforce",
                model="text-embedding-ada-002"
            )
            elapsed_time = (datetime.now() - start_time).total_seconds()
            
            # Vérification de la réponse
            if response.data and len(response.data) > 0 and len(response.data[0].embedding) > 0:
                embedding_size = len(response.data[0].embedding)
                logger.info(f"Test OpenAI réussi - taille embedding: {embedding_size}, temps: {elapsed_time:.2f}s")
                service.set_status(
                    SystemStatus.GREEN,
                    f"Connexion OpenAI opérationnelle (taille embedding: {embedding_size}, temps: {elapsed_time:.2f}s)",
                    {
                        "embedding_size": embedding_size,
                        "response_time": elapsed_time,
                        "model": "text-embedding-ada-002"
                    }
                )
            else:
                logger.warning(f"Réponse OpenAI invalide - contenu: {response}")
                service.set_status(
                    SystemStatus.ORANGE,
                    "Réponse OpenAI invalide",
                    {
                        "response": str(response),
                        "response_time": elapsed_time
                    }
                )
                
        except Exception as e:
            import traceback
            error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "api_key_length": len(OPENAI_API_KEY) if OPENAI_API_KEY else 0,
                "api_key_valid_format": bool(OPENAI_API_KEY and OPENAI_API_KEY.startswith("sk-"))
            }
            
            logger.error(f"Erreur lors de la vérification de OpenAI: {str(e)}")
            logger.error(f"Type d'erreur: {type(e).__name__}")
            logger.error(f"Stack trace: {traceback.format_exc()}")
            
            service.set_status(
                SystemStatus.RED,
                f"Erreur de connexion OpenAI: {str(e)}",
                error_details
            )
    
    async def check_qdrant(self) -> None:
        """Vérifie la connexion à Qdrant"""
        service = self.services["qdrant"]
        
        if not QDRANT_URL or not QDRANT_API_KEY:
            missing_configs = []
            if not QDRANT_URL:
                missing_configs.append("QDRANT_URL")
            if not QDRANT_API_KEY:
                missing_configs.append("QDRANT_API_KEY")
                
            logger.error(f"Vérification Qdrant: Configuration incomplète - variables manquantes: {', '.join(missing_configs)}")
            service.set_status(
                SystemStatus.RED,
                f"Configuration Qdrant incomplète: {', '.join(missing_configs)}",
                {"url_configured": bool(QDRANT_URL), "api_key_configured": bool(QDRANT_API_KEY)}
            )
            return
        
        try:
            logger.info(f"Démarrage de la vérification Qdrant: {QDRANT_URL}...")
            
            # Vérifier la connectivité réseau basique avant d'initialiser le client
            import socket
            import requests
            network_tests = {}
            
            # Test DNS et connectivité socket
            try:
                from urllib.parse import urlparse
                parsed_url = urlparse(QDRANT_URL)
                hostname = parsed_url.netloc.split(":")[0]
                port = parsed_url.port or (443 if parsed_url.scheme == 'https' else 80)
                
                logger.debug(f"Test DNS pour {hostname}...")
                socket_start = datetime.now()
                ip_address = socket.gethostbyname(hostname)
                network_tests["ip_address"] = ip_address
                
                logger.debug(f"Test socket pour {hostname}:{port}...")
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                socket_result = sock.connect_ex((hostname, port))
                sock.close()
                socket_time = (datetime.now() - socket_start).total_seconds()
                
                network_tests["socket_test"] = {
                    "result": socket_result == 0,
                    "time": socket_time,
                    "port": port,
                    "error_code": socket_result
                }
                
                if socket_result == 0:
                    logger.info(f"Test socket réussi pour {hostname}:{port}")
                else:
                    logger.warning(f"Échec du test socket pour {hostname}:{port}: code {socket_result}")
            except Exception as net_err:
                logger.error(f"Erreur lors du test réseau: {str(net_err)}")
                network_tests["network_error"] = str(net_err)
            
            # Test HTTP simple
            try:
                logger.debug(f"Test HTTP vers {QDRANT_URL}...")
                http_start = datetime.now()
                response = requests.get(QDRANT_URL, timeout=5)
                http_time = (datetime.now() - http_start).total_seconds()
                
                network_tests["http_test"] = {
                    "status_code": response.status_code,
                    "time": http_time
                }
                
                logger.info(f"Test HTTP réussi: code {response.status_code}, temps: {http_time:.2f}s")
            except Exception as http_err:
                logger.error(f"Erreur lors du test HTTP: {str(http_err)}")
                network_tests["http_error"] = str(http_err)
            
            # Initialiser le client Qdrant
            logger.debug(f"Initialisation du client Qdrant avec URL={QDRANT_URL}, timeout=10s...")
            client = AsyncQdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=10)
            
            # Vérifier que Qdrant répond
            logger.debug("Récupération de la liste des collections...")
            collections_start = datetime.now()
            collections = await client.get_collections()
            collections_time = (datetime.now() - collections_start).total_seconds()
            
            collection_names = [c.name for c in collections.collections]
            logger.info(f"Collections trouvées: {collection_names}")
            
            # Vérifier si la collection existe
            collection_info = {}
            if QDRANT_COLLECTION in collection_names:
                logger.debug(f"Collection {QDRANT_COLLECTION} trouvée, récupération du nombre de points...")
                count_start = datetime.now()
                count = await client.count(collection_name=QDRANT_COLLECTION)
                count_time = (datetime.now() - count_start).total_seconds()
                
                collection_info["points_count"] = count.count
                collection_info["count_time"] = count_time
                
                logger.info(f"Collection {QDRANT_COLLECTION} contient {count.count} points")
                
                # Faire une recherche simple pour vérifier la fonctionnalité complète
                logger.debug(f"Test de recherche dans {QDRANT_COLLECTION}...")
                test_vector = [0.0] * VECTOR_SIZE
                search_start = datetime.now()
                search_result = await client.search(
                    collection_name=QDRANT_COLLECTION,
                    query_vector=test_vector,
                    limit=1
                )
                search_time = (datetime.now() - search_start).total_seconds()
                
                collection_info["search_time"] = search_time
                collection_info["search_results"] = len(search_result)
                
                logger.info(f"Recherche dans {QDRANT_COLLECTION} a retourné {len(search_result)} résultats en {search_time:.2f}s")
                
                service.set_status(
                    SystemStatus.GREEN,
                    f"Connexion Qdrant opérationnelle ({count.count} points, temps: {collections_time:.2f}s)",
                    {
                        "collections": collection_names,
                        "collection_info": collection_info,
                        "network_tests": network_tests,
                        "response_times": {
                            "collections": collections_time,
                            "count": count_time,
                            "search": search_time
                        }
                    }
                )
            else:
                logger.warning(f"Collection {QDRANT_COLLECTION} non trouvée parmi: {collection_names}")
                service.set_status(
                    SystemStatus.ORANGE,
                    f"Collection {QDRANT_COLLECTION} non trouvée",
                    {
                        "available_collections": collection_names,
                        "network_tests": network_tests,
                        "response_time": collections_time
                    }
                )
                
        except Exception as e:
            import traceback
            error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "qdrant_url": QDRANT_URL,
                "api_key_length": len(QDRANT_API_KEY) if QDRANT_API_KEY else 0
            }
            
            logger.error(f"Erreur lors de la vérification de Qdrant: {str(e)}")
            logger.error(f"Type d'erreur: {type(e).__name__}")
            logger.error(f"Stack trace: {traceback.format_exc()}")
            
            service.set_status(
                SystemStatus.RED,
                f"Erreur de connexion Qdrant: {str(e)}",
                error_details
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
