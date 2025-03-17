"""
Script de diagnostic pour le projet Bioforce
"""
import asyncio
import os
import sys
import inspect
import traceback
from datetime import datetime
from pathlib import Path

# Ajouter le répertoire courant au path pour les importations
sys.path.append(os.path.abspath('.'))

async def test_imports():
    """Teste les importations des modules principaux"""
    print("\n=== Test des importations ===")
    modules = [
        "bioforce_scraper.config",
        "bioforce_scraper.utils.logger",
        "bioforce_scraper.utils.content_tracker",
        "bioforce_scraper.utils.qdrant_connector",
        "bioforce_scraper.utils.embeddings",
        "bioforce_scraper.faq_scraper",
        "bioforce_scraper.scheduler",
        "bioforce_scraper.api.app"
    ]
    
    success = True
    for module_name in modules:
        try:
            print(f"Importation de {module_name}...", end=" ")
            module = __import__(module_name, fromlist=["*"])
            print("OK")
        except Exception as e:
            print(f"ÉCHEC: {e}")
            success = False
    
    return success

async def test_qdrant_connection():
    """Teste la connexion à Qdrant"""
    print("\n=== Test de connexion à Qdrant ===")
    try:
        from bioforce_scraper.utils.qdrant_connector import QdrantConnector
        from bioforce_scraper.config import QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION
        
        print(f"URL Qdrant configurée: {QDRANT_URL}")
        print(f"API Key configurée: {'Oui' if QDRANT_API_KEY else 'Non'}")
        print(f"Collection cible: {QDRANT_COLLECTION}")
        
        connector = QdrantConnector()
        print("Vérification de l'existence de la collection...")
        exists = await connector.ensure_collection_exists()
        print(f"Collection existante ou créée: {exists}")
        
        return True
    except Exception as e:
        print(f"Erreur lors du test de Qdrant: {e}")
        traceback.print_exc()
        return False

async def test_playwright():
    """Teste l'initialisation de Playwright"""
    print("\n=== Test de Playwright ===")
    try:
        from playwright.async_api import async_playwright
        
        print("Importation de Playwright réussie")
        print("Initialisation de Playwright...")
        
        async with async_playwright() as p:
            print("Création d'un navigateur chromium...")
            browser = await p.chromium.launch(headless=True)
            print("Création d'un contexte...")
            context = await browser.new_context()
            print("Création d'une page...")
            page = await context.new_page()
            print("Navigation vers google.com...")
            await page.goto("https://www.google.com")
            print("Page chargée avec succès")
            print("Fermeture du navigateur...")
            await browser.close()
            print("Test Playwright terminé avec succès")
        
        return True
    except Exception as e:
        print(f"Erreur lors du test de Playwright: {e}")
        traceback.print_exc()
        return False

async def test_faq_initialization():
    """Teste l'initialisation du scraper de FAQ"""
    print("\n=== Test d'initialisation du scraper de FAQ ===")
    try:
        from bioforce_scraper.faq_scraper import FAQScraper
        
        scraper = FAQScraper()
        print("Instance de FAQScraper créée")
        
        print("Initialisation du scraper...")
        init_result = await scraper.initialize()
        print(f"Résultat de l'initialisation: {init_result}")
        
        if scraper.browser:
            print("Browser Playwright créé avec succès")
        if scraper.page:
            print("Page Playwright créée avec succès")
        
        print("Fermeture du scraper...")
        await scraper.close()
        print("Scraper fermé avec succès")
        
        return True
    except Exception as e:
        print(f"Erreur lors du test d'initialisation du scraper: {e}")
        traceback.print_exc()
        return False

async def test_fastapi():
    """Teste l'importation et la création de l'application FastAPI"""
    print("\n=== Test de FastAPI ===")
    try:
        from bioforce_scraper.api.app import app
        from fastapi import FastAPI
        
        print("Application FastAPI importée avec succès")
        print(f"Routes configurées: {len(app.routes)}")
        
        for route in app.routes:
            print(f"  - {route.path} [{', '.join(route.methods)}]")
        
        return True
    except Exception as e:
        print(f"Erreur lors du test de FastAPI: {e}")
        traceback.print_exc()
        return False

async def run_tests():
    """Exécute tous les tests de diagnostic"""
    print("=== Diagnostics du projet Bioforce ===")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Répertoire courant: {os.path.abspath('.')}")
    
    # Test des importations
    import_success = await test_imports()
    print(f"\nRésultat des importations: {'✅' if import_success else '❌'}")
    
    # Test de Qdrant
    qdrant_success = await test_qdrant_connection()
    print(f"\nRésultat de Qdrant: {'✅' if qdrant_success else '❌'}")
    
    # Test de Playwright
    playwright_success = await test_playwright()
    print(f"\nRésultat de Playwright: {'✅' if playwright_success else '❌'}")
    
    # Test d'initialisation du scraper
    faq_init_success = await test_faq_initialization()
    print(f"\nRésultat d'initialisation du scraper: {'✅' if faq_init_success else '❌'}")
    
    # Test de FastAPI
    fastapi_success = await test_fastapi()
    print(f"\nRésultat de FastAPI: {'✅' if fastapi_success else '❌'}")
    
    # Résultat global
    all_success = import_success and qdrant_success and playwright_success and faq_init_success and fastapi_success
    print(f"\n=== Résultat global: {'✅ Tous les tests ont réussi' if all_success else '❌ Certains tests ont échoué'} ===")

if __name__ == "__main__":
    asyncio.run(run_tests())
