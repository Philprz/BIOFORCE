"""
Script de test pour vérifier la recherche dans Qdrant
"""
import asyncio
import logging
from bioforce_api_chatbot import search_knowledge_base, initialize_qdrant_client

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_search():
    """Teste la recherche dans la base de connaissances"""
    logger.info("Initialisation du client Qdrant...")
    connection_success = await initialize_qdrant_client()
    
    if not connection_success:
        logger.error("❌ Échec de connexion à Qdrant. Test interrompu.")
        return
        
    logger.info("Connexion à Qdrant établie avec succès.")
    
    query = "formation humanitaire"
    logger.info(f"Recherche pour: '{query}'")
    
    results = await search_knowledge_base(query, limit=3)
    
    if results:
        logger.info(f"✅ {len(results)} résultats trouvés:")
        for i, result in enumerate(results, 1):
            logger.info(f"\nRésultat {i} (score: {result.get('score', 'N/A')}):")
            
            # Afficher les clés disponibles pour le débogage
            logger.info(f"Clés disponibles: {list(result.keys())}")
            
            # Accéder aux champs de manière sécurisée
            question = result.get('question', 'Non disponible')
            answer = result.get('answer', 'Non disponible')
            category = result.get('category', 'Non disponible')
            url = result.get('url', 'Non disponible')
            
            logger.info(f"Question: {question}")
            if answer and len(answer) > 150:
                logger.info(f"Réponse: {answer[:150]}...")
            else:
                logger.info(f"Réponse: {answer}")
            logger.info(f"Catégorie: {category}")
            logger.info(f"URL: {url}")
    else:
        logger.error("❌ Aucun résultat trouvé. Vérifiez la connexion à Qdrant et la collection.")

if __name__ == "__main__":
    asyncio.run(test_search())
