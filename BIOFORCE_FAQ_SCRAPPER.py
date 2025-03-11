import requests
import sqlite3
import os
import json
import dotenv
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time

# ✅ Charger le fichier .env
load_dotenv('C:\\BIOFORCE\\BUILD\\.env')
api_key = os.getenv("OPENAI_API_KEY")

# ✅ Configuration de la base de données
def init_db(db_name="scraping_data.db"):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Vérification et création de la table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            category TEXT,
            title TEXT,
            text TEXT,
            scrape_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Vérification de l'existence de la colonne 'category'
    cursor.execute("PRAGMA table_info(pages)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'category' not in columns:
        cursor.execute("ALTER TABLE pages ADD COLUMN category TEXT")

    conn.commit()
    return conn

# ✅ Fonction pour nettoyer le texte
def clean_text(text):
    text = " ".join(text.split())
    return text[:3000]  # Limite à 3000 caractères

# ✅ Fonction pour extraire la catégorie à partir de la page
def get_category(soup):
    try:
        category = soup.find('div', class_='category')
        if category:
            return category.get_text(strip=True)
        body = soup.find('body')
        body_class = body.get('class', '') if body else ''        
        if body_class:
            if 'learn' in body_class:
                return 'learn'
            if 'build' in body_class:
                return 'build'
        return "unknown"
    except Exception as e:
        print(f"⚠️ Erreur lors de l'extraction de la catégorie : {e}")
        return "unknown"

# ✅ Fonction pour extraire les données d'une page
def scrape_page(url):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            print(f"⚠️ Erreur {response.status_code} : {url}")
            return None

        try:
            soup = BeautifulSoup(response.content.decode('utf-8', 'ignore'), 'lxml')
        except Exception:
            soup = BeautifulSoup(response.content.decode('utf-8', 'ignore'), 'html5lib')



        # Extraire le titre
        title_tag = soup.find('h1')
        title = title_tag.get_text(strip=True) if title_tag else "Sans titre"

        # Extraire la catégorie
        category = get_category(soup)

        # Extraire le texte principal
        content_tag = soup.find('div', class_='content')
        text = clean_text(content_tag.get_text()) if content_tag else "Contenu non disponible"

        data = {
            "url": url,
            "category": category,
            "title": title,
            "text": text
        }

        return data

    except Exception as e:
        print(f"⚠️ Erreur lors de l'extraction de la page {url} : {e}")
        return None

# ✅ Fonction pour sauvegarder dans la base de données
def save_to_db(conn, data):
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO pages (url, category, title, text)
            VALUES (?, ?, ?, ?)
        """, (data["url"], data["category"], data["title"], data["text"]))
        conn.commit()
        print(f"✅ Données sauvegardées pour {data['url']}")
    except Exception as e:
        print(f"⚠️ Erreur lors de la sauvegarde : {e}")

# ✅ Fonction pour sauvegarder dans un fichier JSON
def save_to_json(data, filename="scraped_data.json"):
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✅ Données sauvegardées dans {filename}")
    except Exception as e:
        print(f"⚠️ Erreur lors de la sauvegarde JSON : {e}")

# ✅ Fonction pour explorer automatiquement les sous-pages
def explore_links(base_url, max_depth=3):
    visited = set()
    to_visit = [(base_url, 0)]

    while to_visit:
        url, depth = to_visit.pop()
        if url in visited or depth > max_depth:
            continue

        print(f"🔎 Exploration : {url} (profondeur {depth})")
        visited.add(url)

        data = scrape_page(url)
        if data:
            save_to_db(conn, data)

        try:
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                continue

            soup = BeautifulSoup(response.content, 'html.parser')
            for link in soup.find_all('a', href=True):
                href = link['href']
                full_url = urljoin(url, href)
                parsed = urlparse(full_url)

                # ✅ Suivre uniquement les liens internes
                if parsed.netloc == urlparse(base_url).netloc and full_url not in visited:
                    to_visit.append((full_url, depth + 1))

        except Exception as e:
            print(f"⚠️ Erreur lors de l'exploration des liens : {e}")

        # ✅ Pause pour éviter une surcharge de requêtes
        time.sleep(1)

# ✅ Fonction principale
def main():
    global conn
    conn = init_db()
    start_urls = [
        "https://www.bioforce.org/faq/"
    ]

    all_data = []

    for url in start_urls:
        explore_links(url)

    conn.close()

if __name__ == "__main__":
    main()
