"""
Test ciblé pour vérifier la recherche Qdrant avec des questions de FAQ
Ce script teste l'efficacité de la recherche sur la collection BIOFORCE
"""
import asyncio
import os
import numpy as np
from dotenv import load_dotenv
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
import uuid

# Chargement des variables d'environnement
load_dotenv()
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "BIOFORCE")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Client OpenAI et Qdrant
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
qdrant_client = AsyncQdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

# Questions de FAQ fréquemment posées sur le site
FAQ_QUESTIONS = [
    "Comment s'inscrire à une formation chez Bioforce ?",
    "Quelles sont les modalités de financement disponibles ?",
    "Comment se déroulent les formations à distance ?",
    "Quand commencent les prochaines sessions de formation ?",
    "Est-ce que Bioforce propose des stages ou alternances ?"
]

# Échantillon de données pour les nouveaux documents (si nécessaire)
SAMPLE_FAQS = [
    {
        "question": "Comment s'inscrire à une formation chez Bioforce ?",
        "answer": "Pour vous inscrire à une formation Bioforce, rendez-vous sur notre site web et cliquez sur la formation qui vous intéresse. Suivez les étapes d'inscription en ligne et soumettez votre candidature. Notre équipe vous contactera ensuite pour les prochaines étapes du processus.",
        "category": "formation",
        "language": "fr"
    },
    {
        "question": "Quelles sont les modalités de financement disponibles ?",
        "answer": "Bioforce propose plusieurs options de financement : prise en charge par un tiers (employeur, Pôle Emploi, région), financements internationaux (bourses), ou autofinancement avec possibilité d'échelonnement. Contactez notre service des admissions pour un accompagnement personnalisé sur les financements adaptés à votre situation.",
        "category": "financement",
        "language": "fr"
    },
    {
        "question": "Comment se déroulent les formations à distance ?",
        "answer": "Les formations à distance de Bioforce combinent des cours en ligne sur notre plateforme e-learning, des classes virtuelles en direct avec les formateurs, et des travaux pratiques individuels ou en groupe. Un tuteur vous accompagne tout au long de votre parcours pour assurer votre progression et répondre à vos questions.",
        "category": "formation",
        "language": "fr"
    },
    {
        "question": "Quand commencent les prochaines sessions de formation ?",
        "answer": "Les dates de démarrage des formations varient selon les programmes. Les formations métier démarrent généralement en septembre/octobre, et les formations courtes ont plusieurs sessions tout au long de l'année. Consultez le calendrier des formations sur notre site web pour connaître les dates précises de chaque programme.",
        "category": "formation",
        "language": "fr"
    },
    {
        "question": "Est-ce que Bioforce propose des stages ou alternances ?",
        "answer": "Bioforce intègre des périodes d'application pratique dans la plupart de ses formations métier. Ces périodes peuvent prendre la forme de stages conventionnés ou d'alternance selon le programme. Nos équipes pédagogiques vous accompagnent dans la recherche et la validation de ces expériences professionnelles.",
        "category": "formation",
        "language": "fr"
    }
]

async def generate_embedding(text, normalized=True):
    """Génère un embedding normalisé avec OpenAI"""
    try:
        response = await openai_client.embeddings.create(
            input=text,
            model="text-embedding-ada-002"
        )
        vector = response.data[0].embedding
        
        # Normalisation pour distance cosinus
        if normalized:
            norm = np.linalg.norm(vector)
            if norm > 0:
                vector = [v/norm for v in vector]
                
        return vector
    except Exception as e:
        print(f"Erreur lors de la génération de l'embedding: {e}")
        return None

async def test_search(query, limit=3):
    """Teste la recherche avec et sans normalisation"""
    print("\n" + "="*80)
    print(f"TEST DE RECHERCHE: '{query}'")
    print("="*80)
    
    # Générer l'embedding standard
    vector = await generate_embedding(query)
    if not vector:
        print("❌ Échec de génération de l'embedding")
        return
    
    # 1. Recherche standard
    print("\n1. RECHERCHE STANDARD")
    try:
        results = await qdrant_client.search(
            collection_name=COLLECTION_NAME,
            query_vector=vector,
            limit=limit
        )
        
        if results:
            print(f"Trouvé {len(results)} résultats")
            for i, result in enumerate(results, 1):
                print(f"  {i}. Score: {result.score:.6f}")
                print(f"     Titre: {result.payload.get('title', 'Sans titre')[:100]}")
                if 'question' in result.payload:
                    print(f"     Question: {result.payload.get('question')[:100]}")
        else:
            print("❌ Aucun résultat trouvé")
            
    except Exception as e:
        print(f"❌ Erreur lors de la recherche: {e}")

async def add_sample_faqs():
    """Ajoute des exemples de FAQ à la collection"""
    print("\n" + "="*80)
    print("AJOUT D'EXEMPLES DE FAQ")
    print("="*80)
    
    points = []
    
    for faq in SAMPLE_FAQS:
        # Créer un texte combiné pour l'embedding
        text = f"{faq['question']}\n\n{faq['answer']}"
        
        # Générer l'embedding
        vector = await generate_embedding(text)
        
        if vector:
            # Créer un ID unique
            doc_id = str(uuid.uuid4())
            
            # Préparer le payload
            payload = {
                "title": faq["question"],
                "content": faq["answer"],
                "category": faq["category"],
                "type": "faq",
                "language": faq["language"],
                "source_url": f"https://www.bioforce.org/faq/#{faq['question'].lower().replace(' ', '-')}"
            }
            
            # Ajouter à la liste des points
            points.append({
                "id": doc_id,
                "vector": vector,
                "payload": payload
            })
    
    if points:
        try:
            # Vérifier si la collection existe
            collections = await qdrant_client.get_collections()
            collection_names = [c.name for c in collections.collections]
            
            if COLLECTION_NAME not in collection_names:
                # Créer la collection
                await qdrant_client.create_collection(
                    collection_name=COLLECTION_NAME,
                    vectors_config=models.VectorParams(
                        size=1536,
                        distance=models.Distance.COSINE
                    )
                )
                print(f"Collection {COLLECTION_NAME} créée")
            
            # Insérer les points
            response = await qdrant_client.upsert(
                collection_name=COLLECTION_NAME,
                points=points
            )
            
            print(f"✅ {len(points)} exemples de FAQ ajoutés à la collection {COLLECTION_NAME}")
            return True
            
        except Exception as e:
            print(f"❌ Erreur lors de l'ajout des exemples: {e}")
            return False
    else:
        print("❌ Aucun embedding généré")
        return False

async def check_collection(collection_name):
    """Vérifie si la collection existe et contient des données"""
    try:
        collections = await qdrant_client.get_collections()
        collection_names = [c.name for c in collections.collections]
        
        if collection_name not in collection_names:
            print(f"❌ La collection {collection_name} n'existe pas")
            return False
        
        collection_info = await qdrant_client.get_collection(collection_name=collection_name)
        print(f"Collection {collection_name}: {collection_info.vectors_count} vecteurs")
        
        if not collection_info.vectors_count or collection_info.vectors_count == 0:
            print(f"⚠️ La collection {collection_name} est vide")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la vérification de la collection: {e}")
        return False

async def main():
    """Fonction principale"""
    print("TEST DE RECHERCHE QDRANT AVEC FAQ")
    print("=" * 80)
    
    # Vérifier que la collection existe et contient des données
    collection_exists = await check_collection(COLLECTION_NAME)
    
    if not collection_exists:
        print("La collection est vide ou n'existe pas. Ajout d'exemples de FAQ...")
        added = await add_sample_faqs()
        if not added:
            print("❌ Impossible d'ajouter les exemples. Fin du test.")
            return
    
    # Tester la recherche avec chaque question
    for question in FAQ_QUESTIONS:
        await test_search(question)
        
    print("\nTEST TERMINÉ")

if __name__ == "__main__":
    asyncio.run(main())
