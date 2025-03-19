"""
Test de multiples questions pour évaluer la pertinence des réponses de Qdrant
"""
import asyncio
import json
import os
import time
from dotenv import load_dotenv
from qdrant_client import AsyncQdrantClient
from openai import AsyncOpenAI

# Chargement des variables d'environnement
load_dotenv()
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "BIOFORCE")

# Initialisation des clients
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
qdrant_client = None

# Liste des questions à tester
QUESTIONS = [
    {
        "id": 1,
        "category": "générale",
        "question": "Comment puis-je postuler à une formation chez Bioforce ?",
    },
    {
        "id": 2,
        "category": "frais",
        "question": "Quel est le montant des frais de sélection pour une candidature ?",
    },
    {
        "id": 3,
        "category": "processus",
        "question": "Quelles sont les étapes du processus de sélection ?",
    },
    {
        "id": 4,
        "category": "délais",
        "question": "Combien de temps faut-il pour recevoir une réponse après avoir soumis ma candidature ?",
    },
    {
        "id": 5,
        "category": "prérequis",
        "question": "Quelles sont les conditions d'admission pour la formation en logistique humanitaire ?",
    },
    {
        "id": 6,
        "category": "technique",
        "question": "Comment puis-je modifier mes informations personnelles dans mon espace candidat ?",
    },
    {
        "id": 7,
        "category": "problèmes courants",
        "question": "J'ai oublié mon mot de passe, comment le réinitialiser ?",
    },
    {
        "id": 8,
        "category": "spécifique",
        "question": "Quelle est la durée de la formation de Responsable de Projets Eau, Hygiène et Assainissement ?",
    },
    {
        "id": 9,
        "category": "financements",
        "question": "Est-il possible d'obtenir une bourse ou un financement pour suivre une formation ?",
    },
    {
        "id": 10,
        "category": "après-formation",
        "question": "Quel est le taux d'insertion professionnelle après une formation chez Bioforce ?",
    },
]

async def generate_embedding(text):
    """Génère un embedding pour le texte donné"""
    response = await openai_client.embeddings.create(
        input=text,
        model="text-embedding-ada-002"
    )
    return response.data[0].embedding

async def search_with_query(query, limit=3):
    """Recherche avec une query textuelle"""
    # Générer l'embedding pour la requête
    vector = await generate_embedding(query)
    
    # Recherche avec l'embedding
    results = await qdrant_client.search(
        collection_name=COLLECTION_NAME,
        query_vector=vector,
        limit=limit
    )
    
    return results

async def test_questions():
    """Teste les questions et analyse les résultats"""
    global qdrant_client
    
    # Initialiser le client Qdrant
    print(f"Connexion à Qdrant: {QDRANT_URL} | Collection: {COLLECTION_NAME}")
    qdrant_client = AsyncQdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    
    # Vérifier la connexion
    collections = await qdrant_client.get_collections()
    collection_names = [c.name for c in collections.collections]
    print(f"Collections disponibles: {', '.join(collection_names)}")
    print(f"Début des tests sur {len(QUESTIONS)} questions...\n")
    
    all_results = []
    
    # Tester chaque question
    for question_data in QUESTIONS:
        question_id = question_data["id"]
        category = question_data["category"]
        query = question_data["question"]
        
        print(f"\n[{question_id}] QUESTION ({category}): {query}")
        
        try:
            # Mesurer le temps de réponse
            start_time = time.time()
            results = await search_with_query(query)
            end_time = time.time()
            
            # Formatage des résultats pour la question
            question_results = {
                "question_id": question_id,
                "category": category,
                "query": query,
                "response_time_ms": round((end_time - start_time) * 1000),
                "results_count": len(results),
                "top_results": []
            }
            
            # Analyser les résultats
            print(f"✓ {len(results)} résultats trouvés en {question_results['response_time_ms']} ms")
            
            for i, result in enumerate(results, 1):
                # Extraire les informations du résultat
                score = result.score
                payload = result.payload
                
                # Ajouter le résultat au dictionnaire
                result_data = {
                    "position": i,
                    "score": score,
                    "question": payload.get("question", "N/A"),
                    "answer": payload.get("answer", "N/A")[:200] + "..." if payload.get("answer") and len(payload.get("answer")) > 200 else payload.get("answer", "N/A"),
                    "category": payload.get("category", "N/A"),
                    "url": payload.get("url", "N/A")
                }
                
                question_results["top_results"].append(result_data)
                
                # Afficher un résumé du résultat
                print(f"\nRésultat {i} (score: {score:.4f}):")
                print(f"Q: {result_data['question'][:100]}...")
                print(f"A: {result_data['answer'][:100]}...")
                print(f"Cat: {result_data['category']}")
            
            all_results.append(question_results)
            
        except Exception as e:
            print(f"❌ Erreur lors de la recherche: {str(e)}")
            all_results.append({
                "question_id": question_id,
                "category": category,
                "query": query,
                "error": str(e)
            })
        
        # Pause pour éviter de surcharger l'API
        await asyncio.sleep(1)
    
    # Écrire tous les résultats dans un fichier JSON
    with open("questions_analysis.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    print("\n✅ Analyse terminée et sauvegardée dans 'questions_analysis.json'")
    
    # Analyse globale
    print("\n----- ANALYSE GLOBALE -----")
    success_count = sum(1 for r in all_results if "error" not in r)
    avg_results = sum(r.get("results_count", 0) for r in all_results if "error" not in r) / max(success_count, 1)
    avg_time = sum(r.get("response_time_ms", 0) for r in all_results if "error" not in r) / max(success_count, 1)
    
    print(f"Questions traitées avec succès: {success_count}/{len(QUESTIONS)}")
    print(f"Nombre moyen de résultats par question: {avg_results:.1f}")
    print(f"Temps de réponse moyen: {avg_time:.1f} ms")
    
    # Analyse de cohérence
    print("\n----- ANALYSE DE COHÉRENCE -----")
    categories_with_answers = {}
    
    for result in all_results:
        if "error" not in result and "top_results" in result:
            category = result["category"]
            
            # Évaluer la pertinence des résultats
            has_relevant_result = False
            for top_result in result["top_results"]:
                # Un résultat avec un score > 0.6 est considéré comme pertinent
                if top_result["score"] > 0.6:
                    has_relevant_result = True
                    break
            
            if category not in categories_with_answers:
                categories_with_answers[category] = {"total": 0, "with_relevant": 0}
            
            categories_with_answers[category]["total"] += 1
            if has_relevant_result:
                categories_with_answers[category]["with_relevant"] += 1
    
    # Afficher les résultats par catégorie
    for category, stats in categories_with_answers.items():
        relevant_percentage = (stats["with_relevant"] / stats["total"]) * 100 if stats["total"] > 0 else 0
        print(f"Catégorie '{category}': {relevant_percentage:.1f}% de réponses pertinentes ({stats['with_relevant']}/{stats['total']})")

if __name__ == "__main__":
    asyncio.run(test_questions())
