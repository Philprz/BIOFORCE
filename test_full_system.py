"""
Test complet du système Bioforce
Ce script teste tous les composants du système pour vérifier leur bon fonctionnement.
"""
import os
import json
import logging
import asyncio
import argparse
from dotenv import load_dotenv
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient

# Configuration du logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_system")

# Chargement des variables d'environnement
load_dotenv('.env')

# Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
QDRANT_URL = os.getenv('QDRANT_URL')
QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')
COLLECTION_NAME = os.getenv('QDRANT_COLLECTION', 'BIOFORCE')

# Initialisation des clients
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
qdrant_client = AsyncQdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

class TestResult:
    """Classe pour stocker les résultats des tests"""
    def __init__(self):
        self.tests = {}
        self.failures = 0
        self.successes = 0
    
    def add_result(self, test_name, success, message=None, details=None):
        self.tests[test_name] = {
            "success": success,
            "message": message or "",
            "details": details or {}
        }
        if success:
            self.successes += 1
        else:
            self.failures += 1
    
    def summary(self):
        return {
            "total": self.successes + self.failures,
            "successes": self.successes,
            "failures": self.failures,
            "success_rate": f"{self.successes/(self.successes + self.failures)*100:.1f}%" if (self.successes + self.failures) > 0 else "N/A",
            "tests": self.tests
        }
    
    def print_summary(self):
        summary = self.summary()
        print("\n" + "="*50)
        print(f"RÉSUMÉ DES TESTS: {summary['successes']}/{summary['total']} réussis ({summary['success_rate']})")
        print("="*50)
        
        for test_name, result in self.tests.items():
            status = "✅ RÉUSSI" if result["success"] else "❌ ÉCHEC"
            print(f"{status} - {test_name}: {result['message']}")

async def test_env_variables(result):
    """Vérifie que les variables d'environnement sont bien définies"""
    test_name = "Variables d'environnement"
    logger.info(f"Test: {test_name}")
    
    missing_vars = []
    if not OPENAI_API_KEY:
        missing_vars.append("OPENAI_API_KEY")
    if not QDRANT_URL:
        missing_vars.append("QDRANT_URL")
    if not QDRANT_API_KEY:
        missing_vars.append("QDRANT_API_KEY")
    
    if missing_vars:
        result.add_result(
            test_name, 
            False, 
            f"Variables manquantes: {', '.join(missing_vars)}"
        )
        return False
    
    result.add_result(test_name, True, "Toutes les variables d'environnement requises sont définies")
    return True

async def test_openai_connection(result):
    """Teste la connexion à l'API OpenAI"""
    test_name = "Connexion OpenAI"
    logger.info(f"Test: {test_name}")
    
    try:
        # Test simple d'embeddings
        response = await openai_client.embeddings.create(
            input="Ceci est un test de connexion",
            model="text-embedding-ada-002"
        )
        
        # Vérification que la réponse contient un embedding
        if response.data and len(response.data) > 0 and response.data[0].embedding:
            embedding_size = len(response.data[0].embedding)
            result.add_result(
                test_name, 
                True, 
                f"Connexion à OpenAI réussie (taille embedding: {embedding_size})",
                {"embedding_size": embedding_size}
            )
            return True
        else:
            result.add_result(test_name, False, "Réponse OpenAI invalide")
            return False
            
    except Exception as e:
        result.add_result(test_name, False, f"Erreur de connexion: {str(e)}")
        return False

async def test_qdrant_connection(result):
    """Teste la connexion à Qdrant"""
    test_name = "Connexion Qdrant"
    logger.info(f"Test: {test_name}")
    
    try:
        # Vérifier que Qdrant répond
        collections = await qdrant_client.get_collections()
        collection_names = [c.name for c in collections.collections]
        
        result.add_result(
            test_name, 
            True, 
            f"Connexion à Qdrant réussie ({len(collection_names)} collections)",
            {"collections": collection_names}
        )
        return True
    except Exception as e:
        result.add_result(test_name, False, f"Erreur de connexion: {str(e)}")
        return False

async def test_qdrant_collection(result):
    """Teste que la collection spécifiée existe dans Qdrant"""
    test_name = "Collection Qdrant"
    logger.info(f"Test: {test_name}")
    
    try:
        # Vérifier que la collection existe
        collections = await qdrant_client.get_collections()
        collection_names = [c.name for c in collections.collections]
        
        if COLLECTION_NAME in collection_names:
            # Obtenir des informations sur la collection
            collection_info = await qdrant_client.get_collection(collection_name=COLLECTION_NAME)
            
            # Compter les points dans la collection
            count = await qdrant_client.count(collection_name=COLLECTION_NAME)
            
            result.add_result(
                test_name, 
                True, 
                f"Collection {COLLECTION_NAME} trouvée ({count.count} points)",
                {
                    "count": count.count,
                    "vector_size": collection_info.config.params.vectors.size,
                    "collection_name": COLLECTION_NAME
                }
            )
            return True
        else:
            result.add_result(
                test_name, 
                False, 
                f"Collection {COLLECTION_NAME} non trouvée",
                {"available_collections": collection_names}
            )
            return False
    except Exception as e:
        result.add_result(test_name, False, f"Erreur lors de la vérification: {str(e)}")
        return False

async def test_qdrant_search(result):
    """Teste la recherche dans Qdrant"""
    test_name = "Recherche Qdrant"
    logger.info(f"Test: {test_name}")
    
    try:
        # Générer un embedding
        query = "Comment s'inscrire à une formation?"
        
        response = await openai_client.embeddings.create(
            input=query,
            model="text-embedding-ada-002"
        )
        vector = response.data[0].embedding
        
        # Faire une recherche
        search_result = await qdrant_client.search(
            collection_name=COLLECTION_NAME,
            query_vector=vector,
            limit=3,
            with_payload=True
        )
        
        if search_result and len(search_result) > 0:
            result.add_result(
                test_name, 
                True, 
                f"Recherche réussie ({len(search_result)} résultats)",
                {"query": query, "results_count": len(search_result)}
            )
            return True
        else:
            result.add_result(
                test_name, 
                False, 
                "Aucun résultat trouvé",
                {"query": query}
            )
            return False
    except Exception as e:
        result.add_result(test_name, False, f"Erreur lors de la recherche: {str(e)}")
        return False

async def run_all_tests():
    """Exécute tous les tests disponibles"""
    logger.info("=== DÉMARRAGE DES TESTS DU SYSTÈME ===")
    
    result = TestResult()
    
    # Tests variables d'environnement
    env_ok = await test_env_variables(result)
    if not env_ok:
        logger.error("Variables d'environnement manquantes, impossible de continuer les tests")
        return result
    
    # Test OpenAI
    await test_openai_connection(result)
    
    # Tests Qdrant
    qdrant_conn_ok = await test_qdrant_connection(result)
    if qdrant_conn_ok:
        await test_qdrant_collection(result)
        await test_qdrant_search(result)
    
    logger.info("=== TESTS TERMINÉS ===")
    return result

async def main():
    parser = argparse.ArgumentParser(description="Test du système Bioforce")
    parser.add_argument("--verbose", "-v", action="store_true", help="Affiche plus de détails")
    parser.add_argument("--json", "-j", action="store_true", help="Sortie au format JSON")
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    result = await run_all_tests()
    
    if args.json:
        print(json.dumps(result.summary(), indent=2, ensure_ascii=False))
    else:
        result.print_summary()
    
    # Retourner un code d'erreur si des tests ont échoué
    return 1 if result.failures > 0 else 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
