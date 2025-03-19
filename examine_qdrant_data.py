"""
Examen des données dans les collections Qdrant
"""
import asyncio
import json
import os
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
        
        # Utiliser la méthode scroll correctement
        print(f"\nUtilisation de la méthode scroll pour récupérer {sample_size} points...")
        
        try:
            # La méthode scroll retourne un tuple (points, next_page_offset)
            scroll_response = await client.scroll(
                collection_name=collection_name,
                limit=sample_size,
                with_payload=True,
                with_vectors=False
            )
            
            # Extraire les points du tuple retourné
            if isinstance(scroll_response, tuple) and len(scroll_response) > 0:
                points = scroll_response[0]
                print(f"Récupération de {len(points)} points par scroll")
            else:
                print("Format de réponse scroll inattendu:", type(scroll_response))
                points = []
        except Exception as e:
            print(f"Erreur pendant scroll: {str(e)}")
            points = []
        
        if not points:
            print("\nEssai avec une recherche par similarité...")
            
            # Créer un vecteur de test (rempli de valeurs constantes)
            test_vector = [0.1] * 1536  # Dimension pour les embeddings OpenAI
            
            # Recherche par similarité
            try:
                search_results = await client.query_points(
                    collection_name=collection_name,
                    query_vector=test_vector,
                    limit=sample_size
                )
                
                if hasattr(search_results, 'scored_points'):
                    points = search_results.scored_points
                    print(f"Récupération de {len(points)} points par recherche de similarité.")
                else:
                    print("Format de réponse query_points inattendu:", type(search_results))
                    
                    # Essayer de parcourir directement la réponse si c'est possible
                    if hasattr(search_results, '__iter__'):
                        points = list(search_results)
                        print(f"Extraction de {len(points)} points de la réponse itérable.")
                    else:
                        print("Aucun résultat exploitable trouvé.")
                        return
            except Exception as e:
                print(f"Erreur pendant query_points: {str(e)}")
                return
        
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
