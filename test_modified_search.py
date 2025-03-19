"""
Test de la fonction search_knowledge_base modifiée
"""
import asyncio
import json
from bioforce_api_chatbot import search_knowledge_base, initialize_qdrant_client
import logging

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_search():
    """Teste la fonction de recherche modifiée"""
    logger.info("Initialisation du client Qdrant...")
    await initialize_qdrant_client()
    logger.info("Client Qdrant initialisé.")
    
    # Liste des requêtes à tester
    queries = [
        "Comment puis-je postuler à une formation chez Bioforce ?",
        "Quel est le montant des frais de sélection pour une candidature ?",
        "Quelles sont les conditions d'admission pour la formation en logistique humanitaire ?"
    ]
    
    # Tester chaque requête
    results_file = open("search_results_modified.json", "w", encoding="utf-8")
    results_file.write("[\n")
    
    for i, query in enumerate(queries):
        logger.info(f"\n--- TEST {i+1}: {query} ---")
        
        # Effectuer la recherche
        results = await search_knowledge_base(query, limit=3)
        
        # Afficher les résultats
        if results:
            logger.info(f"✓ {len(results)} résultats trouvés")
            
            for j, result in enumerate(results, 1):
                logger.info(f"\nRésultat {j} (score: {result.get('score', 'N/A'):.4f}):")
                
                # Afficher les champs clés
                title = result.get('question', 'Non disponible')
                content = result.get('answer', 'Non disponible')
                category = result.get('category', 'Non disponible')
                url = result.get('url', 'Non disponible')
                
                logger.info(f"TITRE: {title[:200]}..." if len(str(title)) > 200 else f"TITRE: {title}")
                logger.info(f"CONTENU: {content[:200]}..." if len(str(content)) > 200 else f"CONTENU: {content}")
                logger.info(f"CATÉGORIE: {category}")
                logger.info(f"URL: {url}")
            
            # Sauvegarder les résultats au format JSON
            query_results = {
                "query": query,
                "results": results
            }
            
            results_file.write(json.dumps(query_results, ensure_ascii=False, indent=2))
            if i < len(queries) - 1:
                results_file.write(",\n")
            
        else:
            logger.info("❌ Aucun résultat trouvé")
    
    results_file.write("\n]")
    results_file.close()
    logger.info("\n✅ Résultats sauvegardés dans 'search_results_modified.json'")

if __name__ == "__main__":
    asyncio.run(test_search())
