"""
Script de test pour le scraper de FAQ
"""
import asyncio
import sys
import os
from pathlib import Path

# Ajout du répertoire courant au path pour les importations
sys.path.append(os.path.abspath('.'))

async def test_faq_scraper():
    try:
        print("Importation du module FAQScraper...")
        from bioforce_scraper.faq_scraper import FAQScraper
        
        print("Création d'une instance de FAQScraper...")
        scraper = FAQScraper()
        
        print("Lancement du scraping de la FAQ...")
        await scraper.run()
        
        print("Scraping de la FAQ terminé avec succès!")
        return True
    except Exception as e:
        print(f"Erreur lors du test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=== Test du scraper de FAQ ===")
    success = asyncio.run(test_faq_scraper())
    
    if success:
        print("\n Le test a réussi!")
    else:
        print("\n Le test a échoué!")
