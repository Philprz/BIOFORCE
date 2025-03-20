"""
Script pour vérifier les doublons dans la base Qdrant
Identifie les documents ayant la même URL (doublons exacts) et ceux ayant un contenu similaire (doublons potentiels)
"""
import asyncio
import sys
import pathlib
import collections

# Ajouter le répertoire parent au path pour pouvoir importer les modules
sys.path.append(str(pathlib.Path(__file__).parent))

from bioforce_scraper.utils.qdrant_connector import QdrantConnector
from bioforce_scraper.config import LOG_FILE, QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION
from bioforce_scraper.utils.logger import setup_logger
from qdrant_client import models

# Configuration du logger
logger = setup_logger("check_duplicates", LOG_FILE)

async def get_all_documents(qdrant_connector, collection_name, batch_size=100):
    """
    Récupère tous les documents d'une collection Qdrant
    
    Args:
        qdrant_connector: Instance de QdrantConnector
        collection_name: Nom de la collection
        batch_size: Taille des lots pour la récupération
        
    Returns:
        list: Liste de tous les documents
    """
    documents = []
    offset = None  # Commencer avec offset=None pour la première page
    
    while True:
        try:
            # Utiliser scroll pour parcourir tous les documents
            # scroll n'est pas une méthode async, pas besoin de await
            result = qdrant_connector.client.scroll(
                collection_name=collection_name,
                limit=batch_size,
                offset=offset,
                with_payload=True,
                with_vectors=False  # Pas besoin des vecteurs pour cette vérification
            )
            
            # Extraire les points et le prochain offset
            points, next_offset = result
            
            if not points:
                break  # Plus de documents à récupérer
                
            documents.extend(points)
            logger.info(f"Récupérés {len(documents)} documents")
            
            if next_offset is None:
                break  # Fin de la pagination
                
            offset = next_offset
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des documents: {str(e)}")
            break
            
    return documents

def find_exact_duplicates(documents):
    """
    Trouve les documents ayant exactement la même URL
    
    Args:
        documents: Liste de documents
        
    Returns:
        dict: Dictionnaire des doublons avec URL comme clé et liste des IDs comme valeur
    """
    url_to_ids = collections.defaultdict(list)
    
    for doc in documents:
        # Extraire l'URL et l'ID du document
        url = doc.payload.get("source_url", "")
        if url:
            url_to_ids[url].append(doc.id)
    
    # Ne conserver que les entrées avec plus d'un ID (doublons)
    duplicates = {url: ids for url, ids in url_to_ids.items() if len(ids) > 1}
    
    return duplicates

def analyze_title_duplicates(documents):
    """
    Trouve les documents ayant exactement le même titre
    
    Args:
        documents: Liste de documents
        
    Returns:
        dict: Dictionnaire des doublons avec titre comme clé et liste des IDs comme valeur
    """
    title_to_ids = collections.defaultdict(list)
    
    for doc in documents:
        # Extraire le titre et l'ID du document
        title = doc.payload.get("title", "")
        if title:
            title_to_ids[title].append(doc.id)
    
    # Ne conserver que les entrées avec plus d'un ID (doublons)
    duplicates = {title: ids for title, ids in title_to_ids.items() if len(ids) > 1}
    
    return duplicates

def generate_duplicate_report(exact_duplicates, title_duplicates, documents):
    """
    Génère un rapport sur les doublons trouvés
    
    Args:
        exact_duplicates: Dictionnaire des doublons exacts (même URL)
        title_duplicates: Dictionnaire des doublons potentiels (même titre)
        documents: Liste de tous les documents
        
    Returns:
        str: Rapport formaté
    """
    # Créer un dictionnaire pour accéder rapidement aux documents par ID
    doc_by_id = {doc.id: doc for doc in documents}
    
    report = []
    report.append("=== RAPPORT DE DÉTECTION DE DOUBLONS ===\n")
    
    # Rapport sur le nombre total de documents
    report.append(f"Nombre total de documents: {len(documents)}")
    
    # Rapport sur les doublons exacts (même URL)
    report.append(f"\n=== DOUBLONS EXACTS (MÊME URL): {len(exact_duplicates)} URLS ===")
    if exact_duplicates:
        total_exact_duplicates = sum(len(ids) for ids in exact_duplicates.values()) - len(exact_duplicates)
        report.append(f"Nombre total de documents en doublon exact: {total_exact_duplicates}")
        
        # Afficher un échantillon des doublons exacts (limité pour ne pas surcharger le rapport)
        sample_size = min(10, len(exact_duplicates))
        report.append(f"\nÉchantillon de {sample_size} doublons exacts:")
        
        for i, (url, ids) in enumerate(list(exact_duplicates.items())[:sample_size]):
            report.append(f"\n{i+1}. URL: {url}")
            report.append(f"   Nombre d'instances: {len(ids)}")
            report.append(f"   IDs: {', '.join(ids[:5])}{'...' if len(ids) > 5 else ''}")
    else:
        report.append("Aucun doublon exact trouvé.")
    
    # Rapport sur les doublons potentiels (même titre)
    report.append(f"\n=== DOUBLONS POTENTIELS (MÊME TITRE): {len(title_duplicates)} TITRES ===")
    if title_duplicates:
        total_title_duplicates = sum(len(ids) for ids in title_duplicates.values()) - len(title_duplicates)
        report.append(f"Nombre total de documents avec titre identique: {total_title_duplicates}")
        
        # Afficher un échantillon des doublons potentiels
        sample_size = min(10, len(title_duplicates))
        report.append(f"\nÉchantillon de {sample_size} titres dupliqués:")
        
        for i, (title, ids) in enumerate(list(title_duplicates.items())[:sample_size]):
            # Récupérer les URLs pour ces IDs
            urls = [doc_by_id[doc_id].payload.get("source_url", "N/A") for doc_id in ids[:3]]
            
            report.append(f"\n{i+1}. Titre: {title}")
            report.append(f"   Nombre d'instances: {len(ids)}")
            report.append("   Exemples d'URLs:")
            for j, url in enumerate(urls):
                report.append(f"     {j+1}. {url}")
    else:
        report.append("Aucun doublon potentiel trouvé.")
    
    return "\n".join(report)

async def delete_duplicate_documents(qdrant_connector, collection_name, duplicates_to_delete):
    """
    Supprime les documents en doublon de la collection
    
    Args:
        qdrant_connector: Instance de QdrantConnector
        collection_name: Nom de la collection
        duplicates_to_delete: Liste des IDs de documents à supprimer
        
    Returns:
        int: Nombre de documents supprimés
    """
    if not duplicates_to_delete:
        return 0
        
    try:
        # Supprimer les documents par lots
        batch_size = 100
        deleted_count = 0
        
        for i in range(0, len(duplicates_to_delete), batch_size):
            batch = duplicates_to_delete[i:i+batch_size]
            
            # delete n'est pas une méthode async, pas besoin de await
            qdrant_connector.client.delete(
                collection_name=collection_name,
                points_selector=models.PointIdsList(
                    points=batch
                )
            )
            
            deleted_count += len(batch)
            logger.info(f"Supprimés {deleted_count}/{len(duplicates_to_delete)} documents en doublon")
        
        return deleted_count
    except Exception as e:
        logger.error(f"Erreur lors de la suppression des doublons: {str(e)}")
        return 0

async def main(delete_duplicates=False):
    """
    Fonction principale
    
    Args:
        delete_duplicates: Si True, supprimer les doublons exacts
    """
    # Initialiser le connecteur Qdrant
    qdrant_connector = QdrantConnector(
        url=QDRANT_URL,
        api_key=QDRANT_API_KEY,
        collection_name=QDRANT_COLLECTION
    )
    
    logger.info(f"Vérification des doublons dans la collection {QDRANT_COLLECTION}...")
    
    # Récupérer tous les documents
    logger.info("Récupération de tous les documents...")
    documents = await get_all_documents(qdrant_connector, QDRANT_COLLECTION)
    logger.info(f"Récupérés {len(documents)} documents au total")
    
    # Trouver les doublons exacts
    logger.info("Recherche des doublons exacts (même URL)...")
    exact_duplicates = find_exact_duplicates(documents)
    logger.info(f"Trouvé {len(exact_duplicates)} URLs avec doublons exacts")
    
    # Analyser les titres identiques
    logger.info("Recherche des documents avec titres identiques...")
    title_duplicates = analyze_title_duplicates(documents)
    logger.info(f"Trouvé {len(title_duplicates)} titres dupliqués")
    
    # Générer le rapport
    logger.info("Génération du rapport...")
    report = generate_duplicate_report(exact_duplicates, title_duplicates, documents)
    
    # Écrire le rapport dans un fichier
    report_file = "duplicates_report.txt"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report)
    
    logger.info(f"Rapport écrit dans {report_file}")
    
    # Proposer de supprimer les doublons exacts
    if exact_duplicates:
        # Préparer la liste des documents à supprimer
        # Pour chaque URL en doublon, conserver le document le plus récent
        # et supprimer les autres
        duplicates_to_delete = []
        
        doc_by_id = {doc.id: doc for doc in documents}
        
        for url, ids in exact_duplicates.items():
            if len(ids) <= 1:
                continue
                
            # Trier les documents par timestamp (du plus récent au plus ancien)
            sorted_ids = sorted(
                ids,
                key=lambda id_: doc_by_id[id_].payload.get("timestamp", ""),
                reverse=True
            )
            
            # Conserver le document le plus récent, supprimer les autres
            duplicates_to_delete.extend(sorted_ids[1:])
        
        logger.info(f"Nombre de documents en doublon à supprimer: {len(duplicates_to_delete)}")
        
        # Si l'option --delete est activée, supprimer les doublons
        if delete_duplicates:
            logger.info("Suppression des doublons exacts...")
            deleted_count = await delete_duplicate_documents(
                qdrant_connector,
                QDRANT_COLLECTION,
                duplicates_to_delete
            )
            logger.info(f"Supprimés {deleted_count} documents en doublon")
            
            # Vérification après suppression
            remaining_count = len(documents) - deleted_count
            logger.info(f"Nombre de documents restants dans la collection: {remaining_count}")
        else:
            # Rappel: ce choix sera fait manuellement en consultant le rapport
            logger.info("Consultez le rapport et exécutez avec l'option --delete pour supprimer les doublons exacts")
    
    logger.info("Opération terminée")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Vérifier les doublons dans la base Qdrant")
    parser.add_argument("--delete", action="store_true", help="Supprimer les doublons exacts (conserver le plus récent)")
    
    args = parser.parse_args()
    
    asyncio.run(main(delete_duplicates=args.delete))
