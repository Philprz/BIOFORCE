"""
Configuration pour le scraper Bioforce
"""
import os
from datetime import datetime

# URLs et configuration du site
BASE_URL = "https://www.bioforce.org"
START_URLS = [
    "https://www.bioforce.org/",
    "https://www.bioforce.org/learn/formations-humanitaires/",
    "https://www.bioforce.org/learn/candidature-formation-competence/",
    "https://www.bioforce.org/learn/candidature-formation-metier/",
    "https://www.bioforce.org/learn/financer-ma-formation/",
]

# URLs des sitemaps
SITEMAP_INDEX_URL = "https://www.bioforce.org/sitemap_index.xml"
FAQ_SITEMAP_URL = "https://www.bioforce.org/question-sitemap.xml"

# URLs spécifiques pour la FAQ
FAQ_URLS = [
    "https://www.bioforce.org/question/",
    "https://www.bioforce.org/en/question/"
]

# URLs des pages index de FAQ (pages qui listent les questions)
FAQ_INDEX_URLS = [
    "https://www.bioforce.org/faq/",
    "https://www.bioforce.org/en/faq/"
]

# Patterns pour détecter les URLs de la FAQ
FAQ_PATTERNS = [
    "/question/",
    "/?faq=",
    "/faq-",
    "/faq/"
]

# Patterns à exclure
EXCLUDE_PATTERNS = [
    "/wp-admin/", "/tag/", "/category/", "/author/", 
    "?replytocom=", "?share=", "/feed/", "/comment-page-",
    "/cdn-cgi/", "/wp-json/", ".xml", ".rss", "contact", 
    "sitemap", "mentions-legales", "confidentialite"
]

# Priorité des pages (mots-clés dans l'URL)
PRIORITY_PATTERNS = [
    "formation", "learn", "build", "candidature", "admission", 
    "financement", "logement", "faq", "pdf", "processus"
]

# Structure de répertoire
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
PDF_DIR = os.path.join(OUTPUT_DIR, "pdfs")
DATA_DIR = os.path.join(OUTPUT_DIR, "data")
LOG_DIR = os.path.join(OUTPUT_DIR, "logs")
REPORTS_DIR = os.path.join(OUTPUT_DIR, "reports")

# Configuration technique
REQUEST_DELAY = 1.5  # Delay between requests in seconds
MAX_PAGES = 500      # Maximum number of pages to scrape
PDF_MAX_SIZE = 20 * 1024 * 1024  # 20 MB max PDF size
USER_AGENT = "BioforceBot/1.0 (+https://www.bioforce.org/; Data collection for educational chatbot)"
MAX_LINKS_PER_PAGE = 100  # Nombre maximum de liens à extraire par page
TIMEOUT = 30  # Timeout en secondes pour les requêtes
PROCESSED_URLS_FILE = os.path.join(OUTPUT_DIR, "processed_urls.json")  # Fichier pour stocker les URLs traitées
USE_QDRANT = True  # Utilisation de Qdrant pour stocker les embeddings
DEBUG = False  # Mode debug

# Paramètres supplémentaires pour le mécanisme de retry et gestion des erreurs
MAX_RETRIES = 3       # Nombre maximum de tentatives pour chaque URL
RETRY_DELAY = 2.0     # Délai entre les tentatives en secondes
MAX_TIMEOUT = 45      # Timeout maximum pour les opérations

# Extensions de fichiers à exclure
EXCLUDE_EXTENSIONS = [
    '.jpg', '.jpeg', '.png', '.gif', '.svg', '.mp4', '.webm', '.mp3', 
    '.wav', '.webp', '.ico', '.css', '.js', '.zip', '.gz', '.tar'
]

# Configuration pour l'API externe 
API_HOST = "localhost"
API_PORT = 8000

# Catégories de contenu
CONTENT_CATEGORIES = [
    "formation", "admission", "financement", "logement", 
    "vie_etudiante", "international", "presentation", "faq",
    "contact", "autre"
]

# Format de date pour l'extraction
DATE_FORMAT = "%Y-%m-%d"
CURRENT_DATE = datetime.now().strftime(DATE_FORMAT)

# Langues supportées
SUPPORTED_LANGUAGES = ["fr", "en"]

# Configuration Qdrant
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_HOST = os.getenv("QDRANT_URL", "http://localhost:6333")  # Alias pour QDRANT_URL pour compatibilité
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
VECTOR_SIZE = 1536  # Taille des vecteurs OpenAI
QDRANT_COLLECTION_ALL = "BIOFORCE_ALL"  # Collection pour toutes les données
COLLECTION_NAME_ALL = "BIOFORCE_ALL"  # Alias pour QDRANT_COLLECTION_ALL pour compatibilité
COLLECTION_NAME = "BIOFORCE"
QDRANT_COLLECTION = "BIOFORCE"  # Collection principale pour la connaissance

# Configuration OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
EMBEDDING_MODEL = "text-embedding-ada-002"
COMPLETION_MODEL = "gpt-3.5-turbo"

# Configuration API FastAPI
API_ROOT_PATH = os.getenv("API_ROOT_PATH", "")

# GitHub configuration
VERSION = "1.0.0"
GITHUB_REPO = os.getenv("GITHUB_REPO", "https://github.com/Philprz/BIOFORCE")

API_WORKERS = int(os.getenv("API_WORKERS", "4"))
ENABLE_CORS = True
ALLOWED_ORIGINS = ["*"]  # À restreindre en production

# Configuration du scheduling
SCHEDULER_ENABLED = True
FAQ_UPDATE_CRON = "0 0 * * 0"  # Tous les dimanches à minuit
FULL_SITE_UPDATE_CRON = "0 2 * * 0"  # Tous les dimanches à 2h du matin
REMINDER_INTERVAL_MINUTES = 5  # Intervalle entre les rappels

# Configuration des rappels et relances
REMINDER_MESSAGE = "Avez-vous besoin d'aide pour compléter votre candidature?"
REMINDER_ENABLED = True
FOLLOWUP_EMAIL_TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "followup_email.html")
FOLLOWUP_EMAIL_SUBJECT = "Finalisez votre candidature Bioforce"
FOLLOWUP_DAYS_THRESHOLD = 7  # Envoyer un rappel après 7 jours d'inactivité

# Assurez-vous que les répertoires existent
for directory in [OUTPUT_DIR, PDF_DIR, DATA_DIR, LOG_DIR, REPORTS_DIR]:
    os.makedirs(directory, exist_ok=True)

# Créer le répertoire des templates si non existant
TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
os.makedirs(TEMPLATES_DIR, exist_ok=True)

# Configuration du logging
LOG_FILE = os.path.join(LOG_DIR, f"scraping_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
LOG_LEVEL = "INFO"

# UI/UX Configuration
CHATBOT_DEFAULT_WIDTH = 350
CHATBOT_DEFAULT_HEIGHT = 500
CHATBOT_MIN_WIDTH = 300
CHATBOT_MIN_HEIGHT = 400
CHATBOT_MAX_WIDTH = 800
CHATBOT_MAX_HEIGHT = 800
