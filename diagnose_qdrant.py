"""
Diagnostic ciblé des problèmes dans Qdrant
"""
import asyncio
import os
import json
import numpy as np
from dotenv import load_dotenv
from qdrant_client import AsyncQdrantClient
from openai import AsyncOpenAI

# Chargement des variables d'environnement
load_dotenv()
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "BIOFORCE")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

async def analyze_vector_quality(client, collection_name, sample_size=2):
    """Analyse la qualité des vecteurs"""
    print("\n" + "-"*50)
    print("ANALYSE DE LA QUALITÉ DES VECTEURS")
    print("-"*50)
    
    # Obtenir quelques documents avec leurs vecteurs
    try:
        scroll_response = await client.scroll(
            collection_name=collection_name,
            limit=sample_size,
            with_payload=True,
            with_vectors=True
        )
        
        if isinstance(scroll_response, tuple) and len(scroll_response) > 0:
            points = scroll_response[0]
            print(f"Échantillon: {len(points)} points récupérés")
        else:
            print("Erreur: Format de réponse inattendu")
            return
        
        if not points:
            print("Aucun point trouvé dans la collection")
            return
            
        # Analyse des vecteurs
        for idx, point in enumerate(points):
            print(f"\nPoint #{idx+1}")
            vector = point.vector
            
            if vector:
                # Vérifier la dimension du vecteur
                print(f"Dimension: {len(vector)}")
                
                # Calculer la norme pour vérifier si le vecteur est normalisé
                norm = np.linalg.norm(vector)
                print(f"Norme: {norm:.6f}")
                
                # Dans la similarité cosinus, les vecteurs devraient être normalisés (norme=1)
                if 0.99 < norm < 1.01:
                    print("✅ Vecteur correctement normalisé")
                else:
                    print("❌ PROBLÈME: Vecteur non normalisé - affecte la similarité cosinus")
                
                # Vérifier les valeurs extrêmes
                min_val = min(vector)
                max_val = max(vector)
                print(f"Valeurs min/max: {min_val:.6f} / {max_val:.6f}")
                
                # Statistiques simples sur le vecteur
                avg = sum(vector)/len(vector)
                print(f"Moyenne: {avg:.6f}")
                
                # Afficher le titre du document
                title = point.payload.get("title", "Sans titre")
                print(f"Titre: {title[:50]}...")
            else:
                print("❌ PROBLÈME: Vecteur manquant")
        
    except Exception as e:
        print(f"Erreur: {str(e)}")

async def test_normalized_search(client, openai_client, collection_name):
    """Test de recherche avec normalisation des vecteurs"""
    print("\n" + "-"*50)
    print("TEST DE RECHERCHE AVEC NORMALISATION")
    print("-"*50)
    
    # Question de test
    test_question = "Comment puis-je postuler à une formation chez Bioforce ?"
    print(f"Question: {test_question}")
    
    try:
        # Générer l'embedding pour la question
        embedding_response = await openai_client.embeddings.create(
            input=test_question,
            model="text-embedding-ada-002"
        )
        vector = embedding_response.data[0].embedding
        
        # Mesurer la norme du vecteur
        norm_original = np.linalg.norm(vector)
        print(f"Norme du vecteur original: {norm_original:.6f}")
        
        # Tester la recherche avec le vecteur original
        print("\nRecherche avec le vecteur original:")
        results_original = await client.search(
            collection_name=collection_name,
            query_vector=vector,
            limit=3
        )
        
        for i, result in enumerate(results_original):
            print(f"  Résultat {i+1}: Score={result.score:.6f}, Titre={result.payload.get('title', 'Sans titre')[:50]}...")
        
        # Normaliser le vecteur manuellement
        vector_normalized = [v/norm_original for v in vector]
        norm_check = np.linalg.norm(vector_normalized)
        print(f"\nNorme du vecteur normalisé: {norm_check:.6f}")
        
        # Tester la recherche avec le vecteur normalisé
        print("\nRecherche avec le vecteur normalisé:")
        results_normalized = await client.search(
            collection_name=collection_name,
            query_vector=vector_normalized,
            limit=3
        )
        
        for i, result in enumerate(results_normalized):
            print(f"  Résultat {i+1}: Score={result.score:.6f}, Titre={result.payload.get('title', 'Sans titre')[:50]}...")
            
    except Exception as e:
        print(f"Erreur: {str(e)}")

async def test_search_with_filter(client, openai_client, collection_name):
    """Test de recherche avec filtres"""
    print("\n" + "-"*50)
    print("TEST DE RECHERCHE AVEC FILTRES")
    print("-"*50)
    
    test_question = "Comment puis-je postuler à une formation chez Bioforce ?"
    print(f"Question: {test_question}")
    
    try:
        # Générer l'embedding pour la question
        embedding_response = await openai_client.embeddings.create(
            input=test_question,
            model="text-embedding-ada-002"
        )
        vector = embedding_response.data[0].embedding
        
        # Tester la recherche avec filtre sur la langue (fr)
        print("\nRecherche avec filtre langue=fr:")
        try:
            results_filtered = await client.search(
                collection_name=collection_name,
                query_vector=vector,
                query_filter={
                    "must": [
                        {"key": "language", "match": {"value": "fr"}}
                    ]
                },
                limit=3
            )
            
            for i, result in enumerate(results_filtered):
                print(f"  Résultat {i+1}: Score={result.score:.6f}, Titre={result.payload.get('title', 'Sans titre')[:50]}...")
        except Exception as e:
            print(f"  Erreur avec filtre: {str(e)}")
        
    except Exception as e:
        print(f"Erreur: {str(e)}")

async def main():
    print(f"Diagnostic Qdrant: {QDRANT_URL}")
    
    try:
        # Connexion aux clients
        qdrant_client = AsyncQdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        
        # Liste des collections
        collections = await qdrant_client.get_collections()
        collection_names = [c.name for c in collections.collections]
        print(f"Collections disponibles: {', '.join(collection_names)}")
        
        # 1. Analyser la qualité des vecteurs
        await analyze_vector_quality(qdrant_client, COLLECTION_NAME)
        
        # 2. Tester la recherche avec normalisation
        await test_normalized_search(qdrant_client, openai_client, COLLECTION_NAME)
        
        # 3. Tester la recherche avec filtres
        await test_search_with_filter(qdrant_client, openai_client, COLLECTION_NAME)
        
    except Exception as e:
        print(f"Erreur: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
