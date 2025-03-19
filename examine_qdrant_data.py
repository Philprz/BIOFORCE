"""
Examen des données dans les collections Qdrant
"""
import asyncio
import json
import os
import random
from dotenv import load_dotenv
from qdrant_client import AsyncQdrantClient

# Chargement des variables d'environnement
load_dotenv()
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

async def sample_collection_data(client, collection_name, sample_size=5):
    """Récupère un échantillon de données d'une collection"""
    print("\n" + "="*50)
    print("ANALYSE DE LA COLLECTION: " + collection_name)
    print("="*50)
    
    try:
        # Obtenir les informations sur la collection
        collection_info = await client.get_collection(collection_name=collection_name)
        print("Nombre de vecteurs: " + str(collection_info.vectors_count))
        
        # Récupérer quelques IDs aléatoires pour analyse
        # Pour simplifier, nous utilisons des IDs numériques séquentiels
        # Cette approche pourrait ne pas fonctionner si les IDs ne sont pas numériques
        max_id = min(100, collection_info.vectors_count or 100)  # Limiter à 100 pour éviter les problèmes
        
        if max_id == 0:
            print("Collection vide, aucun vecteur à analyser.")
            return
            
        # Générer des IDs aléatoires dans la plage [1, max_id]
        random_ids = [random.randint(1, max_id) for _ in range(min(sample_size, max_id))]
        
        # Convertir en chaînes de caractères pour compatibilité
        random_ids = [str(id) for id in random_ids]
        
        print("\nRécupération de " + str(len(random_ids)) + " points avec les IDs: " + str(random_ids))
        
        # Récupérer les points
        try:
            points = await client.retrieve(
                collection_name=collection_name,
                ids=random_ids,
                with_payload=True,
                with_vectors=False
            )
            
            if not points:
                print("Aucun point trouvé avec les IDs spécifiés.")
                # Essayer avec une approche différente - recherche par similarité avec un vecteur de test
                print("\nEssai avec une recherche par similarité...")
                
                # Créer un vecteur de test (rempli de valeurs constantes)
                test_vector = [0.1] * 1536  # Dimension pour les embeddings OpenAI
                
                # Recherche par similarité
                search_results = await client.search(
                    collection_name=collection_name,
                    query_vector=test_vector,
                    limit=sample_size
                )
                
                if not search_results:
                    print("Aucun résultat trouvé par recherche de similarité.")
                    return
                    
                # Utiliser les résultats de recherche comme échantillons
                points = search_results
                print("Récupération de " + str(len(points)) + " points par recherche de similarité.")
            
            print("\nAnalyse de " + str(len(points)) + " points:")
            
            # Extraire tous les noms d'attributs uniques
            all_fields = set()
            for point in points:
                payload = getattr(point, 'payload', None)
                if payload:
                    all_fields.update(payload.keys())
            
            # Afficher les statistiques des attributs
            if all_fields:
                print("\nAttributs détectés (" + str(len(all_fields)) + "): " + ', '.join(sorted(all_fields)))
                
                # Analyser chaque attribut
                for field in sorted(all_fields):
                    field_values = []
                    field_missing = 0
                    
                    for point in points:
                        payload = getattr(point, 'payload', {})
                        if payload and field in payload:
                            value = payload[field]
                            if value is not None:
                                field_values.append(value)
                        else:
                            field_missing += 1
                    
                    # Calculer les statistiques
                    completion_rate = 100 * (1 - field_missing / len(points))
                    
                    print("\nAttribut: " + field)
                    print("  Taux de remplissage: " + str(completion_rate) + "%")
                    
                    # Afficher des exemples de valeurs
                    if field_values:
                        # Pour les valeurs textuelles longues, tronquer
                        sample_values = field_values[:2]  # Limiter à 2 exemples
                        formatted_values = []
                        
                        for val in sample_values:
                            if isinstance(val, str) and len(val) > 100:
                                formatted_values.append(val[:100] + "...")
                            else:
                                formatted_values.append(str(val))
                        
                        print("  Exemples de valeurs:")
                        for i, val in enumerate(formatted_values, 1):
                            print("    " + str(i) + ". " + val)
            else:
                print("Aucun attribut trouvé dans les échantillons.")
            
            # Afficher un exemple complet de document
            if points:
                print("\nEXEMPLE DE DOCUMENT COMPLET:")
                
                # Récupérer le payload du premier point
                sample_point = points[0]
                sample_payload = getattr(sample_point, 'payload', {})
                
                if sample_payload:
                    print(json.dumps(sample_payload, indent=2, ensure_ascii=False))
                else:
                    print("Le document ne contient pas de payload.")
                    
                # Afficher l'ID et le score si disponibles
                sample_id = getattr(sample_point, 'id', 'N/A')
                sample_score = getattr(sample_point, 'score', 'N/A')
                print("\nID: " + str(sample_id))
                if hasattr(sample_point, 'score'):
                    print("Score: " + str(sample_score))
            
        except Exception as e:
            print("Erreur lors de la récupération des points: " + str(e))
            
    except Exception as e:
        print("Erreur lors de l'analyse de la collection " + collection_name + ": " + str(e))

async def main():
    """Fonction principale"""
    print("Connexion à Qdrant: " + QDRANT_URL)
    client = AsyncQdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    
    try:
        # Vérifier la connexion
        collections = await client.get_collections()
        collection_names = [c.name for c in collections.collections]
        print("Collections disponibles: " + ', '.join(collection_names))
        
        # Analyser chaque collection
        for collection_name in collection_names:
            await sample_collection_data(client, collection_name)
        
    except Exception as e:
        print("Erreur lors de la connexion ou l'analyse: " + str(e))
    
    print("\nAnalyse terminée.")

if __name__ == "__main__":
    asyncio.run(main())
