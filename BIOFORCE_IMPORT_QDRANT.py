# BIOFORCE_IMPORT_QDRANT.py
import os
import re
import io
import json
import logging
import asyncio
import aiohttp
import hashlib
import uuid
import sys
import gzip
import traceback
import aiosqlite
import numpy as np
import mmap
from datetime import datetime, timezone, UTC
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from pathlib import Path
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient, models
from qdrant_client.http import models as rest
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from dateutil.parser import parse
from typing import List
import pycountry
from functools import lru_cache
from asyncio import Queue
from concurrent.futures import ThreadPoolExecutor
from diskcache import Cache
import heapq

logger = logging.getLogger(__name__)

DATA_SOURCE = os.getenv('DATA_SOURCE', 'json')  # 'json' ou 'db'

async def load_data():
    if DATA_SOURCE == 'json':
        data = await read_json_mmap('scraped_data.json')
    else:
        db_manager = DatabaseManager(DATABASE_PATH)
        await db_manager.connect()
        data = await db_manager.get_existing_data()

async def main():
    await load_data()

# Initialisation du cache pour les embeddings
cache = Cache("./embedding_cache")

# Configuration des queues et du thread pool
QUEUE_SIZE = 1000
embedding_queue = Queue(maxsize=QUEUE_SIZE)
processing_queue = Queue(maxsize=QUEUE_SIZE)
thread_pool = ThreadPoolExecutor(max_workers=4)

# Dictionnaire global pour les modèles spaCy
nlp_models = {}

try:
    import spacy
    if not spacy.util.is_package("fr_core_news_sm"):
        spacy.cli.download("fr_core_news_sm")
except Exception as e:
    logger.warning(f"Erreur lors de l'installation du modèle spaCy: {str(e)}")
from langdetect import detect

# Chargement des variables d'environnement
load_dotenv()

# Configuration des chemins
FOLDER_PATH = os.getenv('FOLDER_PATH')
DATABASE_PATH = os.getenv('DATABASE_PATH')
LOGS_PATH = os.getenv('LOGS_PATH')
PENDING_PATH = os.getenv('PENDING_PATH')
FAILED_PATH = os.getenv('FAILED_PATH')
REPORTS_PATH = os.getenv('REPORTS_PATH')
BACKUP_PATH = os.getenv('BACKUP_PATH', os.path.join(FOLDER_PATH, 'qdrant_backups'))

# Création des dossiers nécessaires
for path in [FOLDER_PATH, DATABASE_PATH, LOGS_PATH, PENDING_PATH, FAILED_PATH, REPORTS_PATH, BACKUP_PATH]:
    if path:
        Path(path).mkdir(parents=True, exist_ok=True)
    else:
        raise ValueError(f"Chemin manquant dans le fichier .env")

# Configuration du logging
class UTFStreamHandler(logging.StreamHandler):
    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            stream.write(msg + self.terminator)
            self.flush()
        except UnicodeEncodeError:
            stream.write(msg.encode('utf-8').decode(stream.encoding, 'replace') + self.terminator)
            self.flush()

class CustomFormatter(logging.Formatter):
    def format(self, record):
        if record.levelno == logging.CRITICAL:
            record.levelname = "Critical"
        elif record.levelno == logging.ERROR:
            record.levelname = "Major"
        elif record.levelno == logging.WARNING:
            record.levelname = "Minor"
        return super().format(record)

log_filename = Path(LOGS_PATH) / f"netsuite_import_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        UTFStreamHandler(sys.stdout)
    ]
)
logging.getLogger().handlers[0].setFormatter(CustomFormatter())

logger = logging.getLogger(__name__)

# Variables d'API et configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
QDRANT_URL = os.getenv('QDRANT_URL')
QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')
QDRANT_COLLECTION_NAME = os.getenv('QDRANT_COLLECTION')

# Paramètres de traitement
BATCH_SIZE = int(os.getenv('BATCH_SIZE', '80'))
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
VECTOR_SIZE = int(os.getenv('VECTOR_SIZE', '1536'))

# Vérification des variables obligatoires
required_vars = [
    'OPENAI_API_KEY', 'QDRANT_URL', 'QDRANT_API_KEY',
    'QDRANT_COLLECTION', 'FOLDER_PATH'
]

for var in required_vars:
    if not os.getenv(var):
        raise ValueError(f"Variable d'environnement manquante : {var}")

# Initialisation des clients
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Variables globales pour le suivi
total_files = 0
total_items = 0
processed_items = 0
upserted_items = 0
skipped_items = 0
error_items = 0
processed_urls = set()
item_details = {}
qdrant_added_urls = set()

# Classes et fonctions optimisées

@dataclass
class QdrantPoint:
    url: str
    vector: List[float]
    payload: Dict[str, Any]
    qdrant_id: str = None

    def __post_init__(self):
        if not self.qdrant_id:
            self.qdrant_id = str(uuid.uuid4())

    def to_qdrant_point(self) -> rest.PointStruct:
        return rest.PointStruct(
            id=self.qdrant_id,
            vector=self.vector,
            payload={
                **self.payload,
                "url": self.url
            }
        )

class QdrantConnectionPool:
    def __init__(self, pool_size: int = 5):
        self.pool = Queue(maxsize=pool_size)
        self._pool_size = pool_size

    async def initialize(self):
        for _ in range(self._pool_size):
            client = AsyncQdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
            await self.pool.put(client)

    async def get(self) -> AsyncQdrantClient:
        return await self.pool.get()

    async def release(self, client: AsyncQdrantClient):
        await self.pool.put(client)

class CheckpointManager:
    def __init__(self, checkpoint_path: str):
        self.checkpoint_path = Path(checkpoint_path)
        self.checkpoint_file = self.checkpoint_path / "checkpoint.json"
        self.checkpoint_data = self._load_checkpoint()

    def _load_checkpoint(self) -> Dict:
        if self.checkpoint_file.exists():
            with open(self.checkpoint_file, 'r') as f:
                return json.load(f)
        return {'processed_urls': [], 'last_batch': 0}

    async def save_checkpoint(self, processed_urls: Set[str], batch_num: int):
        checkpoint = {
            'processed_urls': list(processed_urls),
            'last_batch': batch_num,
            'timestamp': datetime.now().isoformat()
        }
        await asyncio.to_thread(self._write_checkpoint, checkpoint)

    def _write_checkpoint(self, checkpoint: Dict):
        with open(self.checkpoint_file, 'w') as f:
            json.dump(checkpoint, f)

@dataclass(order=True)
class PrioritizedItem:
    priority: int
    item: Any = field(compare=False)

class PriorityBatchProcessor:
    def __init__(self):
        self.queue = []
        self.processing = set()

    def add_item(self, item: Dict, priority: int):
        heapq.heappush(self.queue, PrioritizedItem(priority, item))

    async def process_next_batch(self, batch_size: int) -> List[Dict]:
        batch = []
        while len(batch) < batch_size and self.queue:
            item = heapq.heappop(self.queue).item
            if item['url'] not in self.processing:
                batch.append(item)
                self.processing.add(item['url'])
        return batch

class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = os.path.join(db_path, 'netsuite.db')
        self._pool = []
        self._pool_lock = asyncio.Lock()
        self._pool_size = 5

    async def _create_conn(self):
        conn = await aiosqlite.connect(self.db_path)
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA synchronous=NORMAL")
        await conn.execute("PRAGMA page_size = 4096")
        await conn.execute("PRAGMA cache_size = -2000")
        await conn.execute("PRAGMA temp_store = MEMORY")
        await conn.execute("PRAGMA mmap_size = 30000000000")
        return conn

    async def get_connection(self):
        async with self._pool_lock:
            if not self._pool:
                conn = await self._create_conn()
                self._pool.append(conn)
            return self._pool.pop()

    async def connect(self):
        self.db = await self._create_conn()
        await self.init_database()

    async def init_database(self):
        async with self.db.execute("PRAGMA journal_mode=WAL"):
            pass
        async with self.db.execute("PRAGMA synchronous=NORMAL"):
            pass

        await self.db.execute('''CREATE TABLE IF NOT EXISTS items (
            url TEXT PRIMARY KEY,
            content_hash TEXT NOT NULL,
            title TEXT,
            summary TEXT,
            vector BLOB,
            last_updated TIMESTAMP,
            processing_status TEXT,
            error_message TEXT,
            keywords TEXT,
            countries TEXT
        )''')

        await self.db.execute('''CREATE INDEX IF NOT EXISTS idx_content_hash
                                ON items(content_hash)''')
        await self.db.execute('''CREATE TABLE IF NOT EXISTS processing_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            action TEXT NOT NULL,
            details TEXT,
            FOREIGN KEY (url) REFERENCES items(url)
        )''')

        await self.db.execute('''CREATE INDEX IF NOT EXISTS idx_logs_url_timestamp
                                ON processing_logs(url, timestamp)''')
        await self.db.commit()
        logger.info("Base de données initialisée avec succès")

    async def get_existing_data(self, url: str, content_hash: str) -> Optional[Dict[str, Any]]:
        async with self.db.execute("""
            SELECT content_hash, title, summary, vector, last_updated
            FROM items
            WHERE url = ? AND content_hash = ? AND vector IS NOT NULL
        """, (url, content_hash)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None

            return {
                'content_hash': row[0],
                'title': row[1],
                'summary': row[2],
                'vector': np.frombuffer(row[3], dtype=np.float32).tolist() if row[3] else None,
                'last_updated': row[4]
            }

    async def upsert_item(self, point: QdrantPoint, content_hash: str) -> bool:
        try:
            current_time = int(datetime.now(UTC).timestamp())
            vector_bytes = np.array(point.vector, dtype=np.float32).tobytes()

            await self.db.execute("""
                INSERT INTO items (
                    url, content_hash, title, summary, vector,
                    last_updated, processing_status
                ) VALUES (?, ?, ?, ?, ?, ?, 'completed')
                ON CONFLICT(url) DO UPDATE SET
                    content_hash = excluded.content_hash,
                    title = excluded.title,
                    summary = excluded.summary,
                    vector = excluded.vector,
                    last_updated = excluded.last_updated,
                    processing_status = excluded.processing_status
            """, (
                point.url,
                content_hash,
                point.payload.get('title'),
                point.payload.get('summary'),
                vector_bytes,
                current_time
            ))

            await self.db.commit()
            return True

        except Exception as e:
            logger.error(f"Erreur lors de l'upsert de {point.url}: {str(e)}")
            return False

    async def log_processing(self, url: str, action: str, details: str):
        try:
            await self.db.execute("""
                INSERT INTO processing_logs (url, timestamp, action, details)
                VALUES (?, ?, ?, ?)
            """, (url, datetime.now(UTC).isoformat(), action, details))
            await self.db.commit()
        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement du log pour {url}: {str(e)}")

    async def close(self):
        if self.db:
            await self.db.close()

# Fonctions optimisées

async def load_spacy_models():
    global nlp_models
    nlp_models['fr'] = spacy.load("fr_core_news_sm")

@lru_cache(maxsize=1000)
def get_country_code(country_name: str) -> str:
    try:
        return pycountry.countries.search_fuzzy(country_name)[0].alpha_3
    except:
        return None

async def detect_countries(content: str, title: str, keywords: str) -> List[str]:
    global nlp_models
    countries = set()

    try:
        nlp = nlp_models.get('fr')
        if not nlp:
            return []

        sample_text = f"{title} {content[:2000]} {keywords}"
        doc = nlp(sample_text)

        entities = [(ent.text, ent.label_) for ent in doc.ents if ent.label_ == "GPE"]
        countries.update(filter(None, [get_country_code(ent[0]) for ent in entities]))

        try:
            lang = detect(content)
            if lang:
                countries.add(f"lang_{lang}")
        except Exception as e:
            logger.warning(f"Erreur lors de la détection de langue: {str(e)}")

        return sorted(list(countries))

    except Exception as e:
        logger.error(f"Erreur lors de la détection des pays: {str(e)}")
        try:
            lang = detect(content)
            return [f"lang_{lang}"] if lang else []
        except Exception as sub_e:
            logger.error(f"Erreur lors du fallback de détection de langue: {str(sub_e)}")
            return []

async def embedding_worker():
    while True:
        batch = []
        try:
            while len(batch) < 8:
                item = await embedding_queue.get()
                if item is None:  # Signal de fin
                    break
                batch.append(item)

            if not batch:
                break

            response = await openai_client.embeddings.create(
                input=[item['text'] for item in batch],
                model="text-embedding-ada-002"
            )

            for item, embedding in zip(batch, response.data):
                item['future'].set_result(embedding.embedding)

        except Exception as e:
            for item in batch:
                item['future'].set_exception(e)

async def preprocess_content(content: str) -> str:
    """Prétraite le contenu pour respecter les limites de tokens."""
    if len(content) > 4000:
        try:
            summary_response = await openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Summarize the following content in English, keeping key technical information and terminology:"},
                    {"role": "user", "content": content}
                ],
                max_tokens=1000,
                temperature=0.3,
            )
            return summary_response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Erreur lors du résumé du contenu: {str(e)}")
            return content[:4000]  # Fallback si erreur
    return content

async def generate_embedding(content: str) -> List[float]:
    cache_key = hashlib.md5(content.encode()).hexdigest()

    cached_embedding = cache.get(cache_key)
    if cached_embedding is not None:
        return cached_embedding

    try:
        if len(content) > 4000:
            processed_content = await preprocess_content(content)
        else:
            processed_content = content

        response = await openai_client.embeddings.create(
            input=processed_content,
            model="text-embedding-ada-002"
        )

        embedding = response.data[0].embedding
        cache.set(cache_key, embedding, expire=86400)
        return embedding

    except Exception as e:
        logger.error(f"Erreur d'embedding: {str(e)}")
        raise


async def generate_title_and_summary(content: str, url: str) -> Tuple[str, str, str, str]:
    """
    Generate title, summary, keywords, and detect countries from the content.
    """
    if not content.strip():
        return "Untitled Document", "No summary available", "No keywords", []

    try:
        prompts = [
            ("title", "Generate a clear, concise title (maximum 10 words) for this content:\n\n" + content[:1000]),
            ("summary", "Summarize this content in 3 clear sentences:\n\n" + content),
            ("keywords", "Extract 5-7 key technical terms or concepts from this content, separated by commas:\n\n" + content[:4000])
        ]

        async def process_prompt(prompt_type, prompt_text):
            response = await openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a precise technical documentation assistant."},
                    {"role": "user", "content": prompt_text}
                ],
                max_tokens=150 if prompt_type != "summary" else 300,
                temperature=0.3,
            )
            return prompt_type, response.choices[0].message.content.strip()

        results = await asyncio.gather(*[process_prompt(p_type, p_text) for p_type, p_text in prompts])
        result_dict = dict(results)

        countries = await detect_countries(content, result_dict["title"], result_dict["keywords"])

        return result_dict["title"], result_dict["summary"], result_dict["keywords"], countries

    except Exception as e:
        logger.error(f"Erreur lors de la génération du titre et du résumé: {str(e)}")
        return "Untitled Document", f"Error generating summary: {str(e)}"


async def read_json_mmap(file_path: str) -> list:
    loop = asyncio.get_event_loop()
    
    def _read():
        with open(file_path, 'rb') as f:
            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                return json.loads(mm.read().decode('utf-8'))
                
    try:
        return await loop.run_in_executor(None, _read)
    except Exception as e:
        logger.error(f"Erreur lors de la lecture du fichier {file_path}: {str(e)}")
        return []


async def prepare_qdrant_point(item: Dict[str, Any], db_manager: DatabaseManager) -> Optional[QdrantPoint]:
    try:
        if not item.get('id'):
            item['id'] = str(uuid.uuid4())
            logger.info(f"UUID généré pour item sans ID: {item['id']}")

        url = item.get('url')
        content = item.get('content', item.get('text', '')).strip()

        if not url or not content:
            logger.warning(f"URL ou contenu manquant pour l'item {item['id']}")
            return None

        content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
        existing_data = await db_manager.get_existing_data(url, content_hash)

        if existing_data:
            logger.info(f"Réutilisation des données existantes pour {url}")
            title = existing_data.get('title', 'Untitled Document')
            summary = existing_data.get('summary', 'No summary available')
            keywords = existing_data.get('keywords', 'No keywords')
            countries = existing_data.get('countries', [])

            return QdrantPoint(
                url=url,
                vector=existing_data['vector'],
                payload={
                    'id': item['id'],
                    'title': title,
                    'summary': summary,
                    'keywords': keywords,
                    'countries': countries,
                    'content': content,
                    'content_hash': content_hash,
                    'last_updated': int(datetime.now(UTC).timestamp())
                }
            )

        logger.info(f"Génération de nouvelles données pour {url}")
        try:
            title, summary, keywords, countries = await generate_title_and_summary(content, url)

        except Exception as e:
            logger.error(f"Erreur lors de la génération du titre et du résumé: {str(e)}")
            title, summary, keywords, countries = "Untitled Document", "Summary not available", "No keywords", []

        processed_content = await preprocess_content(content)
        embedding_text = f"{title} {processed_content} {summary}"
        vector = await generate_embedding(embedding_text)

        return QdrantPoint(
            url=url,
            vector=vector,
            payload={
                'id': item['id'],
                'title': title,
                'summary': summary,
                'keywords': keywords,
                'countries': countries,
                'content': content,
                'content_hash': content_hash,
                'last_updated': int(datetime.now(UTC).timestamp())
            }
        )

    except Exception as e:
        logger.error(f"Erreur lors de la préparation du point pour {url}: {str(e)}")
        return None

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    retry=retry_if_exception_type((ResponseHandlingException, UnexpectedResponse)),
    reraise=True
)
async def qdrant_upsert(points: List[QdrantPoint], qdrant_pool: QdrantConnectionPool) -> bool:
    if not points:
        logger.warning("Aucun point à upserter")
        return False

    try:
        qdrant_points = [point.to_qdrant_point() for point in points]

        backup_file = Path(BACKUP_PATH) / f"qdrant_points_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json.gz"
        with gzip.open(backup_file, 'wt', encoding='utf-8') as f:
            json.dump([{
                'id': p.id,
                'vector': p.vector,
                'payload': p.payload
            } for p in qdrant_points], f)

        logger.info(f"Backup sauvegardé dans {backup_file}")

        total_batches = (len(qdrant_points) + BATCH_SIZE - 1) // BATCH_SIZE
        success_count = 0

        client = await qdrant_pool.get()
        try:
            for i in range(0, len(qdrant_points), BATCH_SIZE):
                batch = qdrant_points[i:i + BATCH_SIZE]
                batch_num = i // BATCH_SIZE + 1

                try:
                    await client.upsert(
                        collection_name=QDRANT_COLLECTION_NAME,
                        points=batch,
                        wait=True
                    )
                    success_count += len(batch)
                    for point in batch:
                        qdrant_added_urls.add(point.payload.get("url"))
                    logger.info(f"Lot {batch_num}/{total_batches} upserté avec succès ({len(batch)} points)")
                except Exception as e:
                    logger.error(f"Échec de l'upsert du lot {batch_num}: {str(e)}")
                    return False
        finally:
            await qdrant_pool.release(client)

        return success_count == len(qdrant_points)

    except Exception as e:
        logger.error(f"Erreur lors de l'upsert Qdrant: {str(e)}")
        return False


def is_valid_content(item: Dict[str, Any]) -> bool:
    """Vérifie si le contenu de l'item est pertinent."""

    # Liste de titres à exclure
    excluded_titles = {
        "NetSuite Login",
        "Login",
        "Connexion",
        "Page de connexion",
        "Sign In"
    }

    # Vérification du titre
    title = item.get('title', '').strip()
    if title in excluded_titles:
        logger.info(f"Item exclu - titre non pertinent: {title}")
        return False

    # Vérification longueur minimale du contenu
    content = item.get('content', item.get('text', '')).strip()
    if len(content) < 100:  # Minimum 100 caractères
        logger.info(f"Item exclu - contenu trop court: {len(content)} caractères")
        return False

    return True

async def process_batch(batch_items: List[Dict[str, Any]], db_manager: DatabaseManager, qdrant_pool: QdrantConnectionPool) -> Tuple[int, int]:
    processed = 0
    errors = 0

    try:
        logger.info(f"Début du traitement d'un lot de {len(batch_items)} items")

        prepare_tasks = []
        for item in batch_items:
            if item.get('url') not in processed_urls:
                if not is_valid_content(item):
                    continue
                prepare_tasks.append(prepare_qdrant_point(item, db_manager))

        points = [p for p in await asyncio.gather(*prepare_tasks) if p is not None]

        if points:
            success = await qdrant_upsert(points, qdrant_pool)
            if success:
                for point in points:
                    content_hash = hashlib.md5(point.payload['content'].encode('utf-8')).hexdigest()
                    if await db_manager.upsert_item(point, content_hash):
                        await db_manager.log_processing(point.url, 'upsert', 'Success')
                        processed += 1
                    else:
                        await db_manager.log_processing(point.url, 'error', 'Database upsert failed')
                        errors += 1
            else:
                errors += len(points)
                for point in points:
                    await db_manager.log_processing(point.url, 'error', 'Qdrant upsert failed')

    except Exception as e:
        logger.error(f"Erreur lors du traitement du lot: {str(e)}")
        errors += len(batch_items)

    return processed, errors


async def process_all_items(folder_path: str, mode: str, db_manager: DatabaseManager, checkpoint_manager: CheckpointManager, qdrant_pool: QdrantConnectionPool):
    global total_files, total_items, processed_items, upserted_items, skipped_items, error_items

    try:
        all_files = [f for f in os.listdir(folder_path) if f.endswith('.json')]
        if not all_files:
            logger.warning(f"Aucun fichier JSON trouvé dans {folder_path}")
            return

        total_files = len(all_files)
        logger.info(f"Nombre total de fichiers JSON : {total_files}")

        all_items = []
        for file_name in all_files:
            file_path = os.path.join(folder_path, file_name)
            try:
                items = await read_json_mmap(file_path)
                if isinstance(items, list):
                    all_items.extend(items)
                else:
                    all_items.append(items)
                logger.info(f"Fichier {file_name} chargé avec succès")
            except Exception as e:
                logger.error(f"Erreur lors de la lecture du fichier {file_name}: {str(e)}")
                continue

        total_items = len(all_items)
        logger.info(f"Nombre total d'items à traiter: {total_items}")

        priority_processor = PriorityBatchProcessor()
        for priority, item in enumerate(all_items):
            priority_processor.add_item(item, priority)

        window_size = 3  # Nombre de lots traités simultanément
        while True:
            tasks = []
            for _ in range(window_size):
                batch = await priority_processor.process_next_batch(BATCH_SIZE)
                if not batch:
                    break
                tasks.append(process_batch(batch, db_manager, qdrant_pool))

            if not tasks:
                break

            results = await asyncio.gather(*tasks)
            current_batch = (processed_items + error_items) // BATCH_SIZE

            for processed, errors in results:
                processed_items += processed
                error_items += errors

            await checkpoint_manager.save_checkpoint(processed_urls, current_batch)

    except Exception as e:
        logger.error(f"Erreur lors du traitement des items: {str(e)}")
        raise
    finally:
        report_filename = Path(REPORTS_PATH) / f"netsuite_import_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_filename, 'w', encoding='utf-8') as f:
            f.write(f"=== Rapport d'import NETSUITE ===\n\n")
            f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Mode: {mode}\n")
            f.write(f"Fichiers traités: {total_files}\n")
            f.write(f"Items total: {total_items}\n")
            f.write(f"Items traités: {processed_items}\n")
            f.write(f"Items en erreur: {error_items}\n")
            f.write(f"URLs uniques traitées: {len(processed_urls)}\n")
            f.write(f"URLs ajoutées à Qdrant: {len(qdrant_added_urls)}\n")
            if total_items > 0:
                f.write(f"Taux de réussite: {(len(qdrant_added_urls)/total_items)*100:.2f}%\n")
            else:
                f.write(f"Taux de réussite: 0.00%\n")
        logger.info(f"Rapport d'import généré: {report_filename}")

async def main():
    try:
        logger.info("Démarrage du programme d'import NETSUITE")

        mode = ""
        while mode not in ["overwrite", "update"]:
            mode = input("Choisissez le mode (overwrite/update): ").strip().lower()
            if mode not in ["overwrite", "update"]:
                print("Mode invalide. Veuillez choisir 'overwrite' ou 'update'")

        logger.info(f"Mode sélectionné : {mode}")

        # Initialisation des gestionnaires
        db_manager = DatabaseManager(DATABASE_PATH)
        checkpoint_manager = CheckpointManager(BACKUP_PATH)
        qdrant_pool = QdrantConnectionPool()

        await db_manager.connect()
        await qdrant_pool.initialize()
        await load_spacy_models()

        # Démarrage des workers d'embedding
        embedding_workers = [asyncio.create_task(embedding_worker()) for _ in range(4)]

        try:
            if mode == "overwrite":
                client = await qdrant_pool.get()
                try:
                    try:
                        collection_info = await client.get_collection(QDRANT_COLLECTION_NAME)
                        if collection_info:
                            await client.delete_collection(QDRANT_COLLECTION_NAME)
                            logger.info(f"Collection '{QDRANT_COLLECTION_NAME}' supprimée")

                        await client.create_collection(
                            collection_name=QDRANT_COLLECTION_NAME,
                            vectors_config=models.VectorParams(
                                size=VECTOR_SIZE,
                                distance=models.Distance.COSINE
                            )
                        )
                        logger.info(f"Collection '{QDRANT_COLLECTION_NAME}' créée")
                    except Exception as e:
                        logger.error(f"Erreur lors de la gestion de la collection: {str(e)}")
                        raise
                finally:
                    await qdrant_pool.release(client)
            else:
                client = await qdrant_pool.get()
                try:
                    try:
                        await client.get_collection(QDRANT_COLLECTION_NAME)
                        logger.info(f"Collection '{QDRANT_COLLECTION_NAME}' existante")
                    except Exception as e:
                        logger.error(f"La collection n'existe pas: {str(e)}")
                        raise
                finally:
                    await qdrant_pool.release(client)

            await process_all_items(FOLDER_PATH, mode, db_manager, checkpoint_manager, qdrant_pool)
            logger.info("Traitement terminé avec succès")

        except Exception as e:
            logger.error(f"Erreur lors du traitement: {str(e)}")
            raise
        finally:
            # Arrêt des workers
            for _ in range(4):
                await embedding_queue.put(None)
            await asyncio.gather(*embedding_workers)

            await db_manager.close()

    except Exception as e:
        logger.error(f"Une erreur inattendue s'est produite : {str(e)}")
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Programme interrompu par l'utilisateur")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Erreur critique lors de l'exécution du programme : {str(e)}")
        logger.critical(traceback.format_exc())
        sys.exit(1)