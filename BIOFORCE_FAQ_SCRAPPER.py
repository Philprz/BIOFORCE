# BIOFORCE_FAQ_SCRAPPER.py

import requests
import sqlite3
import os
import json
import time
import dotenv
dotenv.load_dotenv()

from bs4 import BeautifulSoup
from urllib.robotparser import RobotFileParser
from openai import OpenAI
from urllib.parse import urlparse, unquote
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# Configuration de l'API OpenAI
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("La clé API OpenAI n'est pas définie dans les variables d'environnement")

client = OpenAI(api_key=api_key)
# Créez un verrou global pour la sauvegarde en JSON
file_lock = Lock()

def init_db(db_name="scraping_data.db"):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='urls'")
    table_exists = cursor.fetchone() is not None

    if table_exists:
        cursor.execute("PRAGMA table_info(urls)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'last_error' not in columns:
            cursor.execute("ALTER TABLE urls ADD COLUMN last_error TEXT DEFAULT NULL")
            cursor.execute("ALTER TABLE urls ADD COLUMN retry_count INTEGER DEFAULT 0")
            print("Migration: Ajout des colonnes last_error et retry_count à la table urls")
    else:
        cursor.execute("""
            CREATE TABLE urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                depth INTEGER DEFAULT 0,
                scanned BOOLEAN DEFAULT FALSE,
                scan_date TIMESTAMP,
                last_error TEXT DEFAULT NULL,
                retry_count INTEGER DEFAULT 0
            )
        """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            title TEXT,
            text TEXT,
            images TEXT,
            last_modified TEXT,
            etag TEXT,
            content_length TEXT,
            content_type TEXT,
            scrape_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            language TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT,
            src TEXT UNIQUE,
            alt TEXT,
            description TEXT,
            last_modified TEXT,
            etag TEXT,
            content_length TEXT,
            last_check TIMESTAMP,
            status INTEGER DEFAULT 1
        )
    """)
    conn.commit()
    return conn

def save_urls_to_file(urls, filename="urls.json"):
    """Sauvegarde les URLs dans un fichier JSON avec timestamp"""
    try:
        data = {
            "timestamp": datetime.now().isoformat(),
            "urls": list(urls)
        }
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        print(f"URLs sauvegardées dans {filename}")
    except Exception as e:
        print(f"Erreur lors de la sauvegarde des URLs: {e}")

def load_urls_from_file(filename="urls.json"):
    """Charge les URLs depuis un fichier JSON"""
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return set(data.get("urls", []))
    except Exception as e:
        print(f"Erreur lors du chargement des URLs: {e}")
    return set()

def get_scan_progress(conn):
    """Récupère la progression du scan"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN scanned = TRUE THEN 1 ELSE 0 END) as done,
            SUM(CASE WHEN last_error IS NOT NULL THEN 1 ELSE 0 END) as errors
        FROM urls
    """)
    result = cursor.fetchone()
    return {
        "total": result[0] or 0,
        "done": result[1] or 0,
        "errors": result[2] or 0
    }

def is_html_page(response):
    """Vérifie si la réponse est une page HTML"""
    content_type = response.headers.get('content-type', '').lower()
    return 'text/html' in content_type

def get_url_depth(url, start_url):
    """Calcule la profondeur d'une URL par rapport à l'URL de départ"""
    return url.replace(start_url, '').strip('/').count('/')

def is_allowed_url(url, base_domain="bioforce.org", language="", max_depth=5, start_url=None):
    """
    Vérifie si l'URL respecte tous les critères :
    - Domaine correspondant
    - (Optionnel) Langue présente dans l'URL si language est fourni
    - Pas d'ancre ni de paramètres
    - Profondeur inférieure ou égale à max_depth
    """
    try:
        parsed = urlparse(url)
        path = unquote(parsed.path)

        # Vérification du domaine
        domain_ok = parsed.netloc == base_domain or parsed.netloc.endswith('.' + base_domain)

        # Vérification de la langue uniquement si spécifiée
        lang_ok = True if not language else f"/{language}/" in path

        # Éviter les ancres et paramètres
        no_fragment = not parsed.fragment
        no_search = not parsed.query

        # Vérification de la profondeur
        depth_ok = True
        if start_url:
            depth_ok = get_url_depth(url, start_url) <= max_depth

        return all([domain_ok, lang_ok, no_fragment, no_search, depth_ok])
    except Exception:
        return False

def get_image_metadata(src):
    """Récupère les métadonnées d'une image"""
    try:
        response = requests.head(src, timeout=5)
        return {
            'last_modified': response.headers.get('last-modified'),
            'etag': response.headers.get('etag'),
            'content_length': response.headers.get('content-length'),
            'status_code': response.status_code
        }
    except Exception as e:
        print(f"Erreur métadonnées image {src}: {e}")
        return None

def process_image(conn, page_url, img_data):
    """Traite une image individuelle avec gestion des erreurs."""
    cursor = conn.cursor()

    try:
        src = img_data['src']
        metadata = get_image_metadata(src)

        if not metadata:
            return False

        # Vérifier si l'image existe déjà
        cursor.execute("""
            SELECT last_modified, etag, content_length
            FROM images
            WHERE src = ? AND status = 1
        """, (src,))
        existing = cursor.fetchone()

        needs_update = True
        if existing:
            needs_update = (
                metadata['last_modified'] != existing[0] or
                metadata['etag'] != existing[1] or
                metadata['content_length'] != existing[2]
            )

        if needs_update:
            description = analyze_image(src) if metadata['status_code'] == 200 else None

            if description:  # Continuer uniquement si l'analyse réussit
                cursor.execute("""
                    INSERT OR REPLACE INTO images
                    (url, src, alt, description, last_modified, etag,
                     content_length, last_check, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 1)
                """, (
                    page_url,
                    src,
                    img_data['alt'],
                    description,
                    metadata['last_modified'],
                    metadata['etag'],
                    metadata['content_length']
                ))
                conn.commit()
                return True

        return False

    except Exception as e:
        print(f"Erreur traitement image {src}: {e}")
        conn.rollback()
        return False

def get_page_metadata(url):
    """Récupère les métadonnées d'une page"""
    try:
        response = requests.head(url, timeout=5)
        return {
            'last_modified': response.headers.get('last-modified'),
            'etag': response.headers.get('etag'),
            'content_length': response.headers.get('content-length'),
            'content_type': response.headers.get('content-type')
        }
    except Exception as e:
        print(f"Erreur lors de la récupération des métadonnées de {url}: {e}")
        return None

def can_fetch(url, user_agent='*'):
    """Vérifie les permissions dans robots.txt"""
    try:
        base_url = "/".join(url.split("/")[:3])
        robots_url = f"{base_url}/robots.txt"
        rp = RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(user_agent, url)
    except Exception as e:
        print(f"Erreur lors de la vérification de robots.txt pour {url}: {e}")
        return False

def analyze_image(image_url):
    """Analyse une image avec l'API OpenAI et gère les erreurs."""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Décrivez cette image de manière fonctionnelle"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url,
                                "detail": "low"
                            }
                        }
                    ]
                }
            ],
            max_tokens=200
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Erreur lors de l'analyse de l'image {image_url}: {e}")
        return None

def scrape_page(url):
    """Extrait les données d'une page web"""
    SUPPORTED_FORMATS = ['.png', '.jpeg', '.jpg', '.gif', '.webp']

    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200 or not is_html_page(response):
            print(f"Erreur {response.status_code} ou page non HTML pour {url}")
            return None

        soup = BeautifulSoup(response.content, 'html.parser')
        title = soup.title.string.strip() if soup.title else "No Title"
        text = " ".join([p.text.strip() for p in soup.find_all('p')])

        # Détection de la langue (si disponible)
        html_tag = soup.find('html')
        lang = html_tag.get('lang', '') if html_tag else ''

        images = []
        base_url = "/".join(url.split("/")[:-1])

        for img in soup.find_all('img'):
            src = img.get('src', '')
            alt = img.get('alt', 'No description')

            if not any(src.lower().endswith(fmt) for fmt in SUPPORTED_FORMATS):
                continue

            if src.startswith("//"):
                src = "https:" + src
            elif src.startswith("/"):
                src = "/".join(url.split("/")[:3]) + src
            elif not src.startswith(("http://", "https://")):
                src = f"{base_url}/{src}"

            try:
                img_response = requests.head(src, timeout=5)
                if img_response.status_code == 200:
                    description = analyze_image(src)
                    images.append({
                        "src": src,
                        "alt": alt,
                        "description": description or "No detailed description"
                    })
            except Exception as e:
                print(f"Erreur pour l'image {src}: {e}")
                continue

        return {
            "url": url,
            "title": title,
            "text": text,
            "images": images,
            "language": lang
        }
    except Exception as e:
        print(f"Erreur lors du scraping de {url}: {e}")
        return None

def save_to_db(conn, data):
    """Sauvegarde ou met à jour les données dans la base de données"""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO pages
            (url, title, text, images, last_modified, etag, content_length,
             content_type, scrape_date, language)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
        """, (
            data["url"],
            data["title"],
            data["text"],
            json.dumps(data["images"]),
            data.get("last_modified"),
            data.get("etag"),
            data.get("content_length"),
            data.get("content_type"),
            data.get("language")
        ))
        conn.commit()
    except Exception as e:
        print(f"Erreur lors de la sauvegarde en base : {e}")
        conn.rollback()

def scan_all_urls(conn, start_url, user_agent='*', max_retries=3, timeout=10,
                 max_depth=5, base_domain="bioforce.org", language=""):
    """Scanne et stocke toutes les URLs trouvées"""
    start_time = time.time()
    stats = {
       "scanned": 0,
       "errors": 0,
       "skipped": 0,
       "depth_exceeded": 0,
       "url_count": 0
    }

    cursor = conn.cursor()
    to_scan = {(start_url, 0)}  # Tuple (url, profondeur)
    scanned = set()

    # Charger les URLs déjà scannées
    cursor.execute("SELECT url FROM urls WHERE scanned = TRUE")
    scanned.update(row[0] for row in cursor.fetchall())
    stats["url_count"] += len(scanned)

    # Charger les URLs en attente avec leur profondeur
    cursor.execute("SELECT url, depth FROM urls WHERE scanned = FALSE")
    pending_urls = {(row[0], row[1]) for row in cursor.fetchall()}
    to_scan.update(pending_urls)
    stats["url_count"] += len(pending_urls)

    try:
        while to_scan:
            current_url, current_depth = to_scan.pop()

            if current_depth > max_depth:
                stats["depth_exceeded"] += 1
                print(f"[{stats['url_count']}] Profondeur maximum dépassée ({current_depth}) pour: {current_url}")
                continue

            if current_url in scanned:
                stats["skipped"] += 1
                print(f"[{stats['url_count']}] URL déjà scannée: {current_url}")
                continue

            try:
                cursor.execute("SELECT retry_count FROM urls WHERE url = ?", (current_url,))
                result = cursor.fetchone()
                retry_count = result[0] if result else 0

                if not is_allowed_url(current_url, base_domain, language, max_depth, start_url):
                    print(f"[{stats['url_count']}] URL non autorisée: {current_url}")
                    continue

                if not can_fetch(current_url, user_agent):
                    print(f"[{stats['url_count']}] Non autorisé par robots.txt: {current_url}")
                    continue

                if retry_count >= max_retries:
                    print(f"[{stats['url_count']}] Abandonné après {max_retries} tentatives: {current_url}")
                    stats["skipped"] += 1
                    continue

                print(f"[{stats['url_count']}] Scanning {current_url} (profondeur: {current_depth})")
                response = requests.get(current_url, timeout=timeout)

                if not is_html_page(response):
                    print(f"[{stats['url_count']}] Page non HTML ignorée: {current_url}")
                    continue

                soup = BeautifulSoup(response.content, 'html.parser')

                cursor.execute("""
                    INSERT OR REPLACE INTO urls
                    (url, depth, scanned, scan_date, last_error, retry_count)
                    VALUES (?, ?, TRUE, CURRENT_TIMESTAMP, NULL, ?)
                """, (current_url, current_depth, retry_count))

                stats["scanned"] += 1
                scanned.add(current_url)

                for link in soup.find_all('a', href=True):
                    full_url = requests.compat.urljoin(current_url, link['href'])
                    new_depth = current_depth + 1

                    if (full_url not in scanned and
                        (full_url, new_depth) not in to_scan and
                        is_allowed_url(full_url, base_domain, language, max_depth, start_url)):
                        to_scan.add((full_url, new_depth))
                        stats["url_count"] += 1
                        print(f"[{stats['url_count']}] Nouvelle URL trouvée: {full_url}")
                        cursor.execute("""
                            INSERT OR IGNORE INTO urls (url, depth, scanned)
                            VALUES (?, ?, FALSE)
                        """, (full_url, new_depth))

                conn.commit()
                time.sleep(1)

            except KeyboardInterrupt:
                raise
            except Exception as e:
                stats["errors"] += 1
                cursor.execute("""
                    UPDATE urls
                    SET retry_count = retry_count + 1,
                        last_error = ?
                    WHERE url = ?
                """, (str(e), current_url))
                conn.commit()
                print(f"[{stats['url_count']}] Erreur scan URL {current_url}: {e}")

    except KeyboardInterrupt:
        print("\nInterruption détectée. Sauvegarde de l'état...")
    finally:
        duration = time.time() - start_time
        print("\nStatistiques finales:")
        print(f"Total URLs trouvées: {stats['url_count']}")
        print(f"URLs scannées: {stats['scanned']}")
        print(f"URLs ignorées: {stats['skipped']}")
        print(f"URLs trop profondes: {stats['depth_exceeded']}")
        print(f"Erreurs: {stats['errors']}")
        print(f"Durée: {duration:.2f} secondes")

        conn.commit()
        save_urls_to_file(scanned)
        return scanned

def get_new_connection(db_name="scraping_data.db"):
    """Crée une nouvelle connexion à la base de données pour chaque thread."""
    return sqlite3.connect(db_name)

def process_url(url, mode='update'):
    conn = get_new_connection()  # Connexion propre pour ce thread
    try:
        metadata = get_page_metadata(url)
        if not metadata:
            stats["errors"] += 1
            return

        needs_update = True
        cursor = conn.cursor()
        cursor.execute("SELECT url, last_modified, etag FROM pages")
        db_metadata = {row[0]: {'last_modified': row[1], 'etag': row[2]}
                       for row in cursor.fetchall()}

        if url in db_metadata and mode == 'update':
            db_meta = db_metadata[url]
            needs_update = (
                metadata['last_modified'] != db_meta['last_modified'] or
                metadata['etag'] != db_meta['etag']
            )

        if needs_update:
            print(f"Scraping {url}")
            data = scrape_page(url)
            if data:
                # Traitement des images
                for img in data["images"]:
                    if process_image(conn, url, img):
                        stats["images_processed"] += 1
                    else:
                        stats["images_skipped"] += 1

                # Mise à jour de la page avec les métadonnées
                data.update(metadata)
                save_to_db(conn, data)
                save_to_json(data, "scraped_data.json")
                stats["processed"] += 1
            else:
                stats["errors"] += 1

            time.sleep(1)
        else:
            print(f"Page {url} inchangée")
            stats["skipped"] += 1

    except Exception as e:
        print(f"Erreur lors du traitement de {url}: {e}")
    finally:
        conn.close()  # Fermer la connexion après usage

def process_urls(urls, mode='update', max_pages=None):
    """Traite les URLs scannées avec gestion des images"""
    start_time = time.time()
    global stats
    stats = {
        "processed": 0,
        "errors": 0,
        "skipped": 0,
        "images_processed": 0,
        "images_skipped": 0
    }

    try:
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_url = {executor.submit(process_url, url, mode): url for url in urls}
            for future in as_completed(future_to_url):
                future.result()

    except KeyboardInterrupt:
        print("\nInterruption détectée. Sauvegarde de l'état...")
    finally:
        duration = time.time() - start_time
        print(f"\nStatistiques de traitement:")
        print(f"- Pages traitées: {stats['processed']}")
        print(f"- Pages ignorées: {stats['skipped']}")
        print(f"- Erreurs pages: {stats['errors']}")
        print(f"- Images traitées: {stats['images_processed']}")
        print(f"- Images ignorées: {stats['images_skipped']}")
        print(f"- Durée: {duration:.2f} secondes")

    return stats

def save_to_json(data, filename):
    """Sauvegarde les données dans un fichier JSON avec verrou pour éviter les conflits."""
    try:
        def clean_data(obj):
            if isinstance(obj, dict):
                return {k: clean_data(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [clean_data(item) for item in obj]
            elif isinstance(obj, str):
                return obj.encode('ascii', 'ignore').decode('ascii').replace('\n', ' ').replace('\r', ' ')
            else:
                return obj

        temp_filename = f"{filename}.temp"

        with file_lock:
            existing_data = []
            if os.path.exists(filename):
                try:
                    with open(filename, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                except json.JSONDecodeError:
                    print(f"Fichier JSON corrompu, création d'un nouveau fichier")

            cleaned_data = clean_data(data)
            existing_data.append(cleaned_data)

            with open(temp_filename, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, ensure_ascii=True, indent=2)

            os.replace(temp_filename, filename)

    except Exception as e:
        print(f"Erreur lors de la sauvegarde JSON : {e}")
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

def main():
    # Choix des modes de fonctionnement
    mode = input("Choisir le mode (scan/scrape/both): ").lower()
    while mode not in ['scan', 'scrape', 'both']:
        mode = input("Mode invalide. Choisir 'scan', 'scrape' ou 'both': ").lower()

    update_mode = input("Mode de mise à jour (overwrite/update): ").lower()
    while update_mode not in ['overwrite', 'update']:
        update_mode = input("Mode invalide. Choisir 'overwrite' ou 'update': ").lower()

    # Adaptation pour Bioforce : domaine par défaut et absence de filtre de langue
    base_domain = input("Domaine à scraper (défaut: bioforce.org): ").strip() or "bioforce.org"
    language = input("Langue à scraper (laisser vide si non applicable): ").strip()  # chaîne vide par défaut
    max_depth = int(input("Profondeur maximale de scan (défaut: 5): ").strip() or "5")

    db_name = "scraping_data.db"
    conn = init_db(db_name)
    # URL de départ adapté pour Bioforce
    start_url = f"https://{base_domain}/faq/"

    try:
        if mode in ['scan', 'both']:
            print("\nDémarrage du scan...")
            progress = get_scan_progress(conn)
            print(f"État actuel: {progress['done']}/{progress['total']} URLs scannées, {progress['errors']} erreurs")

            urls = scan_all_urls(conn, start_url, max_depth=max_depth,
                               base_domain=base_domain, language=language)
            print(f"Scan terminé: {len(urls)} URLs trouvées")

        if mode in ['scrape', 'both']:
            print("\nDémarrage du scraping...")
            urls = load_urls_from_file()
            if not urls:
                print("Aucune URL trouvée. Lancez d'abord un scan.")
                return
            process_urls(urls, mode=update_mode)

    except KeyboardInterrupt:
        print("\nInterruption détectée. Sauvegarde finale...")
        conn.commit()
    finally:
        conn.close()

if __name__ == "__main__":
    main()



"""
pip install requests
pip install beautifulsoup4
pip install openai

"""