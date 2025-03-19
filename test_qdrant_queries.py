"""
Test de requêtes multiples à Qdrant pour comparer avec les réponses du chatbot
"""
import asyncio
from qdrant_client import AsyncQdrantClient
from openai import AsyncOpenAI
import os
import json
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "BIOFORCE")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Liste des questions à tester
TEST_QUESTIONS = [
    "Comment puis-je postuler à une formation chez Bioforce ?",
    "Quel est le montant des frais de sélection pour une candidature ?",
    "Quelles sont les dates de formation pour le cours de logistique ?",
    "Est-ce que Bioforce propose des formations à distance ?",
    "Quels sont les prérequis pour la formation en finances humanitaires ?",
    "Comment se passe le processus de sélection ?",
    "Quelles sont les possibilités de financement pour les formations ?",
    "Y a-t-il une limite d'âge pour s'inscrire aux formations ?",
    "Combien de temps durent les formations en gestion de projet ?",
    "Existe-t-il un accompagnement pour trouver un stage après la formation ?"
]

async def generate_embedding(text: str, openai_client: AsyncOpenAI) -> list:
    """Génère un embedding pour le texte donné"""
    try:
        response = await openai_client.embeddings.create(
            input=text,
            model="text-embedding-ada-002"
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Erreur d'embedding: {str(e)}")
        raise

async def search_qdrant(client, query, openai_client, limit=10):
    """Exécute une recherche sémantique sur Qdrant"""
    try:
        # Générer l'embedding pour la requête
        embedding = await openai_client.embeddings.create(
            input=query,
            model="text-embedding-ada-002"
        )
        vector = embedding.data[0].embedding
        
        # Utiliser search() qui fonctionne avec query_vector (même si déprécié)
        search_result = await client.search(
            collection_name=COLLECTION_NAME,
            query_vector=vector,
            limit=limit
        )
        
        results = []
        # Adapter au format retourné par search()
        for point in search_result:
            results.append({
                "score": point.score,
                "title": point.payload.get("title", "Sans titre"),
                "content": point.payload.get("content", "Contenu non disponible"),
                "category": point.payload.get("category", ""),
                "url": point.payload.get("source_url", "")
            })
        
        return results
    except Exception as e:
        print(f"Erreur lors de la recherche: {e}")
        return []

async def main():
    print(f"Connexion à Qdrant: {QDRANT_URL} | Collection: {COLLECTION_NAME}")
    qdrant_client = AsyncQdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    
    # Test de connexion
    collections = await qdrant_client.get_collections()
    collection_names = [c.name for c in collections.collections]
    print(f"Collections disponibles: {collection_names}")
    
    if COLLECTION_NAME not in collection_names:
        print(f"ERREUR: La collection {COLLECTION_NAME} n'existe pas!")
        return
    
    print("\n" + "="*80)
    print("RÉSULTATS DES REQUÊTES")
    print("="*80)
    
    # Dictionnaire pour stocker tous les résultats
    all_results = {}
    
    # Traiter chaque question
    for i, question in enumerate(TEST_QUESTIONS, 1):
        print(f"\n{i}. QUESTION: {question}")
        
        # Rechercher dans Qdrant
        results = await search_qdrant(qdrant_client, question, openai_client, limit=10)
        
        if not results:
            print("Aucun résultat trouvé.")
            all_results[question] = []
            continue
        
        print(f"Nombre de résultats: {len(results)}")
        
        # Formater les résultats pour le JSON
        all_results[question] = results
        
        # Afficher un aperçu simple
        for j, result in enumerate(results, 1):
            print(f"  Résultat {j}: {result['title'][:50]}... (score: {result['score']:.4f})")
    
    # Sauvegarder tous les résultats dans un fichier JSON
    output_file = "qdrant_query_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    print(f"\nTous les résultats ont été sauvegardés dans {output_file}")

if __name__ == "__main__":
    asyncio.run(main())
