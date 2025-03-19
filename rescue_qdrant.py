"""
SCRIPT DE SAUVETAGE QDRANT
Ce script va extraire les données de la collection actuelle,
recréer les embeddings correctement, et les réimporter dans 
une nouvelle collection optimisée.
"""
import asyncio
import os
import numpy as np
from dotenv import load_dotenv
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient, models
from tqdm import tqdm

# Chargement des variables d'environnement
load_dotenv()
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
OLD_COLLECTION = os.getenv("QDRANT_COLLECTION", "BIOFORCE")
NEW_COLLECTION = "BIOFORCE_FIXED"  # Nouvelle collection
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialisation des clients
qdrant_client = AsyncQdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Configuration pour l'extraction et la réimportation
BATCH_SIZE = 50  # Nombre de documents traités par lot
EMBEDDING_MODEL = "text-embedding-ada-002"  # Modèle utilisé dans le chatbot

async def generate_embedding(text):
    """Génère un embedding normalisé avec le bon modèle."""
    if not text:
        return None
        
    try:
        # Limiter la taille du texte si nécessaire (limite d'OpenAI)
        if len(text) > 8000:
            text = text[:8000]
            
        # Générer l'embedding avec OpenAI
        response = await openai_client.embeddings.create(
            input=text,
            model=EMBEDDING_MODEL
        )
        
        # Extraire le vecteur
        vector = response.data[0].embedding
        
        # Normaliser le vecteur pour la similarité cosinus
        norm = np.linalg.norm(vector)
        normalized_vector = [v/norm for v in vector] if norm > 0 else vector
        
        return normalized_vector
    except Exception as e:
        print(f"Erreur lors de la génération de l'embedding: {str(e)}")
        return None

async def extract_data_from_collection():
    """Extrait toutes les données de la collection actuelle."""
    print(f"Extraction des données de {OLD_COLLECTION}...")
    
    documents = []
    offset = None
    batch_count = 0
    
    # Extraire tous les documents par lots
    while True:
        try:
            # Obtenir un lot de documents
            scroll_result = await qdrant_client.scroll(
                collection_name=OLD_COLLECTION,
                limit=BATCH_SIZE,
                offset=offset,
                with_payload=True,
                with_vectors=False  # Ne pas récupérer les vecteurs (nous les régénérerons)
            )
            
            # Vérifier si nous avons des résultats
            if isinstance(scroll_result, tuple) and len(scroll_result) > 0:
                points = scroll_result[0]
                next_offset = scroll_result[1]
            else:
                print("Format de réponse inattendu de Qdrant")
                break
                
            if not points:
                print("Extraction terminée.")
                break
                
            # Ajouter les documents au tableau
            for point in points:
                documents.append({
                    "id": point.id,
                    "payload": point.payload
                })
                
            batch_count += 1
            print(f"Lot {batch_count} extrait: {len(points)} documents")
            
            # Mettre à jour l'offset pour la prochaine itération
            offset = next_offset
            
        except Exception as e:
            print(f"Erreur lors de l'extraction: {str(e)}")
            break
            
    print(f"Total: {len(documents)} documents extraits")
    return documents

async def create_new_collection():
    """Crée une nouvelle collection optimisée."""
    print(f"Création de la nouvelle collection {NEW_COLLECTION}...")
    
    try:
        # Vérifier si la collection existe déjà
        collections = await qdrant_client.get_collections()
        existing_collections = [c.name for c in collections.collections]
        
        if NEW_COLLECTION in existing_collections:
            print(f"La collection {NEW_COLLECTION} existe déjà. Suppression...")
            await qdrant_client.delete_collection(collection_name=NEW_COLLECTION)
        
        # Créer la nouvelle collection avec les bons paramètres
        await qdrant_client.create_collection(
            collection_name=NEW_COLLECTION,
            vectors_config=models.VectorParams(
                size=1536,  # Taille des vecteurs d'OpenAI
                distance=models.Distance.COSINE  # Distance cosinus pour la similarité
            )
        )
        
        print(f"Collection {NEW_COLLECTION} créée avec succès")
        return True
    except Exception as e:
        print(f"Erreur lors de la création de la collection: {str(e)}")
        return False

async def reindex_documents(documents):
    """Réindexe les documents dans la nouvelle collection."""
    print(f"Réindexation de {len(documents)} documents...")
    
    # Traiter les documents par lots
    total_batches = (len(documents) + BATCH_SIZE - 1) // BATCH_SIZE
    reindexed_count = 0
    failed_count = 0
    
    for batch_index in range(total_batches):
        start_idx = batch_index * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, len(documents))
        batch = documents[start_idx:end_idx]
        
        print(f"Traitement du lot {batch_index + 1}/{total_batches} ({len(batch)} documents)")
        
        # Préparer les points pour l'insertion
        points_to_insert = []
        
        # Traiter chaque document du lot
        for doc in tqdm(batch):
            try:
                # Extraire les données pertinentes pour l'embedding
                doc_id = doc["id"]
                payload = doc["payload"]
                
                # Pour l'embedding, utiliser le titre et le contenu
                title = payload.get("title", "")
                content = payload.get("content", "")
                
                # Concaténer pour l'embedding
                text_for_embedding = f"{title}\n\n{content}"
                
                # Générer un nouvel embedding
                vector = await generate_embedding(text_for_embedding)
                
                if vector:
                    # Ajouter à la liste des points à insérer
                    points_to_insert.append(models.PointStruct(
                        id=doc_id,
                        vector=vector,
                        payload=payload
                    ))
                    reindexed_count += 1
                else:
                    print(f"Échec de génération d'embedding pour le document {doc_id}")
                    failed_count += 1
                    
            except Exception as e:
                print(f"Erreur lors du traitement du document: {str(e)}")
                failed_count += 1
        
        # Insérer les points dans la nouvelle collection
        if points_to_insert:
            try:
                await qdrant_client.upsert(
                    collection_name=NEW_COLLECTION,
                    points=points_to_insert
                )
                print(f"Lot {batch_index + 1}: {len(points_to_insert)} documents indexés")
            except Exception as e:
                print(f"Erreur lors de l'insertion du lot {batch_index + 1}: {str(e)}")
                failed_count += len(points_to_insert)
                
    print(f"Réindexation terminée: {reindexed_count} documents réussis, {failed_count} échecs")
    return reindexed_count

async def validate_new_collection():
    """Valide la nouvelle collection avec des requêtes de test."""
    print("\n" + "="*50)
    print("VALIDATION DE LA NOUVELLE COLLECTION")
    print("="*50)
    
    # Questions de test typiques
    test_questions = [
        "Comment s'inscrire à une formation chez Bioforce ?",
        "Quelles sont les modalités de financement ?",
        "Comment postuler pour un emploi chez Bioforce ?"
    ]
    
    for question in test_questions:
        print(f"\nQuestion de test: {question}")
        
        try:
            # Générer l'embedding pour la question
            vector = await generate_embedding(question)
            
            # Tester sur l'ancienne collection
            old_results = await qdrant_client.search(
                collection_name=OLD_COLLECTION,
                query_vector=vector,
                limit=3
            )
            
            print(f"Résultats de {OLD_COLLECTION}:")
            for i, result in enumerate(old_results, 1):
                print(f"  {i}. Score: {result.score:.6f}, Titre: {result.payload.get('title', 'Sans titre')[:50]}...")
            
            # Tester sur la nouvelle collection
            new_results = await qdrant_client.search(
                collection_name=NEW_COLLECTION,
                query_vector=vector,
                limit=3
            )
            
            print(f"\nRésultats de {NEW_COLLECTION}:")
            for i, result in enumerate(new_results, 1):
                print(f"  {i}. Score: {result.score:.6f}, Titre: {result.payload.get('title', 'Sans titre')[:50]}...")
                
            # Comparer les scores moyens
            old_avg_score = sum(r.score for r in old_results) / len(old_results) if old_results else 0
            new_avg_score = sum(r.score for r in new_results) / len(new_results) if new_results else 0
            
            print(f"\nScore moyen {OLD_COLLECTION}: {old_avg_score:.6f}")
            print(f"Score moyen {NEW_COLLECTION}: {new_avg_score:.6f}")
            
            if new_avg_score > old_avg_score:
                print("✅ AMÉLIORATION CONFIRMÉE")
            else:
                print("⚠️ Pas d'amélioration détectée")
                
        except Exception as e:
            print(f"Erreur lors du test: {str(e)}")

async def fix_environment_variable():
    """Crée un fichier .env mis à jour pour utiliser la nouvelle collection."""
    try:
        env_file = ".env"
        new_env_content = []
        
        # Lire le fichier .env actuel
        if os.path.exists(env_file):
            with open(env_file, "r") as f:
                lines = f.readlines()
                
            # Modifier la ligne de QDRANT_COLLECTION
            found = False
            for line in lines:
                if line.startswith("QDRANT_COLLECTION="):
                    new_env_content.append(f"QDRANT_COLLECTION={NEW_COLLECTION}\n")
                    found = True
                else:
                    new_env_content.append(line)
                    
            # Ajouter la variable si elle n'existe pas
            if not found:
                new_env_content.append(f"QDRANT_COLLECTION={NEW_COLLECTION}\n")
                
            # Créer une sauvegarde du fichier .env original
            os.rename(env_file, f"{env_file}.bak")
            
            # Écrire le nouveau fichier .env
            with open(env_file, "w") as f:
                f.writelines(new_env_content)
                
            print(f"✅ Variable d'environnement mise à jour: QDRANT_COLLECTION={NEW_COLLECTION}")
            print(f"Une sauvegarde a été créée: {env_file}.bak")
            return True
        else:
            # Créer un nouveau fichier .env
            with open(env_file, "w") as f:
                f.write(f"QDRANT_COLLECTION={NEW_COLLECTION}\n")
            print(f"✅ Nouveau fichier .env créé avec QDRANT_COLLECTION={NEW_COLLECTION}")
            return True
            
    except Exception as e:
        print(f"Erreur lors de la mise à jour du fichier .env: {str(e)}")
        return False

async def main():
    """Fonction principale de sauvetage."""
    print("=" * 80)
    print("OPÉRATION DE SAUVETAGE QDRANT")
    print("=" * 80)
    
    # 1. Extraire les données existantes
    documents = await extract_data_from_collection()
    
    if not documents:
        print("❌ Échec: Aucun document extrait.")
        return
        
    # 2. Créer la nouvelle collection
    collection_created = await create_new_collection()
    
    if not collection_created:
        print("❌ Échec: Impossible de créer la nouvelle collection.")
        return
        
    # 3. Réindexer les documents
    reindexed_count = await reindex_documents(documents)
    
    if reindexed_count == 0:
        print("❌ Échec: Aucun document réindexé.")
        return
        
    # 4. Valider la nouvelle collection
    await validate_new_collection()
    
    # 5. Mettre à jour la variable d'environnement
    updated = await fix_environment_variable()
    
    if updated:
        print("\n" + "=" * 80)
        print("✅ OPÉRATION DE SAUVETAGE RÉUSSIE")
        print("=" * 80)
        print(f"1. {len(documents)} documents extraits de {OLD_COLLECTION}")
        print(f"2. {reindexed_count} documents réindexés dans {NEW_COLLECTION}")
        print(f"3. Variable d'environnement mise à jour: QDRANT_COLLECTION={NEW_COLLECTION}")
        print("\nVous pouvez maintenant relancer votre chatbot avec:")
        print("   python bioforce_api_chatbot.py")
    else:
        print("\n⚠️ Opération partiellement réussie. Vous devez mettre à jour manuellement la variable QDRANT_COLLECTION.")

if __name__ == "__main__":
    asyncio.run(main())
