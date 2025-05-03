import asyncio
import os
import uuid
import logging
from datetime import datetime
from dotenv import load_dotenv
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
import aiohttp
from bs4 import BeautifulSoup

# Charger les variables d'environnement
load_dotenv()

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION")

# Configurer le logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialiser les clients
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
qdrant_client = AsyncQdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

# URLs spécifiques à scraper
SPECIFIC_URLS = [
    "https://bioforce.org/learn/processus-de-selection/",
    "https://bioforce.org/learn/frais-de-selection-et-de-formation/",
    "https://bioforce.org/faq/"
]

async def generate_embedding(text: str):
    """Génère un embedding pour le texte donné"""
    try:
        response = await openai_client.embeddings.create(
            input=text,
            model="text-embedding-ada-002"
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Erreur d'embedding: {str(e)}")
        raise

async def fetch_url(url):
    """Récupère le contenu d'une URL"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    logger.error(f"Erreur HTTP {response.status} pour {url}")
                    return None
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de {url}: {str(e)}")
        return None

async def extract_faq_items(html, url):
    """Extrait les items FAQ d'une page HTML"""
    items = []
    try:
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extraction des FAQ items
        # Cette logique dépend de la structure du site
        faq_items = soup.select('.faq-item, .accordion-item')
        
        for item in faq_items:
            question_elem = item.select_one('.faq-question, .accordion-header')
            answer_elem = item.select_one('.faq-answer, .accordion-body')
            
            if question_elem and answer_elem:
                question = question_elem.get_text(strip=True)
                answer = answer_elem.get_text(strip=True)
                
                items.append({
                    "question": question,
                    "answer": answer,
                    "source_url": url,
                    "category": "FAQ"
                })
        
        # Si pas de structure FAQ spécifique, extraire des paragraphes pertinents
        if not items:
            # Chercher des paragraphes contenant des mots-clés
            keywords = ["frais", "sélection", "candidature", "coût", "tarif", "€", "euro"]
            
            paragraphs = soup.select('p, li, .content-block')
            for p in paragraphs:
                text = p.get_text(strip=True)
                if any(keyword in text.lower() for keyword in keywords):
                    # Extraire le titre de la section si possible
                    heading = None
                    for h in ['h1', 'h2', 'h3', 'h4', 'h5']:
                        prev_heading = p.find_previous(h)
                        if prev_heading:
                            heading = prev_heading.get_text(strip=True)
                            break
                    
                    if heading:
                        items.append({
                            "question": heading,
                            "answer": text,
                            "source_url": url,
                            "category": "Frais et coûts"
                        })
                    else:
                        items.append({
                            "question": "Informations sur les frais",
                            "answer": text,
                            "source_url": url,
                            "category": "Frais et coûts"
                        })
        
        # Ajouter des Q&A explicites pour les frais
        items.append({
            "question": "Quel est le montant des frais de sélection pour une candidature ?",
            "answer": "Les frais de sélection pour une candidature sont de 60€ (ou 20000 CFA pour l'Afrique). Ces frais sont à payer après avoir rempli le formulaire de candidature.",
            "source_url": url,
            "category": "Frais et coûts"
        })
        
        logger.info(f"Extrait {len(items)} items de {url}")
        return items
    
    except Exception as e:
        logger.error(f"Erreur lors de l'extraction depuis {url}: {str(e)}")
        return items

async def main():
    """Fonction principale"""
    try:
        # S'assurer que la collection existe
        collections = await qdrant_client.get_collections()
        collection_names = [c.name for c in collections.collections]
        
        if QDRANT_COLLECTION not in collection_names:
            logger.warning(f"Collection {QDRANT_COLLECTION} n'existe pas, création en cours...")
            await qdrant_client.create_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config=models.VectorParams(
                    size=1536,
                    distance=models.Distance.COSINE
                )
            )
        
        # Traiter chaque URL
        for url in SPECIFIC_URLS:
            logger.info(f"Traitement de {url}")
            html = await fetch_url(url)
            
            if html:
                items = await extract_faq_items(html, url)
                
                # Insérer les items dans Qdrant
                for item in items:
                    # Générer un ID unique
                    point_id = str(uuid.uuid4())
                    
                    # Préparer le texte pour l'embedding
                    text = f"Question: {item['question']} Réponse: {item['answer']}"
                    
                    # Générer l'embedding
                    vector = await generate_embedding(text)
                    
                    # Créer le point Qdrant
                    point = models.PointStruct(
                        id=point_id,
                        vector=vector,
                        payload={
                            "question": item["question"],
                            "answer": item["answer"],
                            "source_url": item["source_url"],
                            "category": item["category"],
                            "timestamp": datetime.now().isoformat()
                        }
                    )
                    
                    # Insérer dans Qdrant
                    await qdrant_client.upsert(
                        collection_name=QDRANT_COLLECTION,
                        points=[point]
                    )
                    
                    logger.info(f"Point inséré: {item['question'][:30]}...")
        
        logger.info("Scraping terminé avec succès")
    
    except Exception as e:
        logger.error(f"Erreur lors du scraping: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())