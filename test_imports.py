"""
Script de test pour vérifier les importations du projet Bioforce
"""
import sys
import os
import importlib
from pathlib import Path

# Ajouter le répertoire courant au chemin d'importation
sys.path.append(os.path.abspath('.'))

def test_import(module_name):
    """Teste l'importation d'un module"""
    print(f"Tentative d'importation de {module_name}... ", end="")
    try:
        module = importlib.import_module(module_name)
        print("Réussi!")
        return True
    except Exception as e:
        print(f"Échec: {str(e)}")
        return False

# Test des importations principales
modules_to_test = [
    "bioforce_scraper",
    "bioforce_scraper.config",
    "bioforce_scraper.utils.logger",
    "bioforce_scraper.utils.content_tracker",
    "bioforce_scraper.utils.language_detector",
    "bioforce_scraper.utils.embeddings",
    "bioforce_scraper.utils.qdrant_connector",
    "bioforce_scraper.utils.reminder_service",
    "bioforce_scraper.faq_scraper",
    "bioforce_scraper.scheduler",
    "bioforce_scraper.api.app"
]

# Exécution des tests
success_count = 0
failed_count = 0

print("\n=== Test des importations du projet Bioforce ===\n")

for module in modules_to_test:
    if test_import(module):
        success_count += 1
    else:
        failed_count += 1

print(f"\n=== Résultat des tests: {success_count} réussis, {failed_count} échoués ===")

if failed_count > 0:
    print("\nConseil: Si les importations échouent, vérifiez que:")
    print("1. Tous les dossiers contiennent un fichier __init__.py")
    print("2. Les chemins d'importation utilisent le préfixe 'bioforce_scraper'")
    print("3. Le répertoire racine du projet est dans sys.path")
