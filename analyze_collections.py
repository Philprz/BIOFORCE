"""
Analyse des collections Qdrant pour comprendre la structure des données
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

# Nombre d'échantillons à extraire de chaque collection
SAMPLE_SIZE = 5

async def analyze_collection(client, collection_name):
    """Analyse une collection Qdrant"""
    print("\n" + "="*50)
    print("ANALYSE DE LA COLLECTION: " + collection_name)
    print("="*50)
    
    try:
        # Obtenir les informations sur la collection
        collection_info = await client.get_collection(collection_name=collection_name)
        vectors_count = collection_info.vectors_count
        
        print("Nombre de vecteurs: " + str(vectors_count))
        print("Configuration des vecteurs: " + str(collection_info.config))
        
        # Lister et compter les attributs disponibles
        print("\nRécupération d'échantillons de documents...")
        
        # Récupérer des points aléatoires pour analyser les attributs
        points = await client.scroll(
            collection_name=collection_name,
            limit=SAMPLE_SIZE,
            with_payload=True,
            with_vectors=False
        )
        
        if not points.points:
            print("Aucun point trouvé dans la collection.")
            return
            
        print("\nAnalyse de " + str(len(points.points)) + " échantillons:")
        
        # Extraire tous les noms d'attributs uniques
        all_fields = set()
        for point in points.points:
            if point.payload:
                all_fields.update(point.payload.keys())
        
        # Afficher les statistiques des attributs
        if all_fields:
            print("\nAttributs détectés (" + str(len(all_fields)) + "): " + ', '.join(sorted(all_fields)))
            
            # Analyser chaque attribut
            for field in sorted(all_fields):
                field_values = []
                field_missing = 0
                
                for point in points.points:
                    if point.payload and field in point.payload:
                        value = point.payload[field]
                        if value is not None:
                            field_values.append(value)
                    else:
                        field_missing += 1
                
                # Calculer les statistiques
                completion_rate = 100 * (1 - field_missing / len(points.points))
                
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
        
        # Recherche d'un exemple complet de document
        print("\nEXEMPLE DE DOCUMENT COMPLET:")
        # Choisir un échantillon aléatoire
        sample_document = random.choice(points.points)
        print(json.dumps(sample_document.payload, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print("Erreur lors de l'analyse de la collection " + collection_name + ": " + str(e))

async def main():
    """Fonction principale pour analyser les collections Qdrant"""
    print("Connexion à Qdrant: " + QDRANT_URL)
    client = AsyncQdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    
    # Vérifier la connexion
    collections = await client.get_collections()
    collection_names = [c.name for c in collections.collections]
    print("Collections disponibles: " + ', '.join(collection_names))
    
    # Analyser chaque collection
    for collection_name in collection_names:
        await analyze_collection(client, collection_name)
    
    print("\nAnalyse terminée.")

if __name__ == "__main__":
    asyncio.run(main())
