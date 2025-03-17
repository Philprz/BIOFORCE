"""
Script pour exécuter le scraper Bioforce sur demande
"""
import asyncio
import argparse
import os
import sys
from datetime import datetime

# Ajouter le répertoire parent au path pour pouvoir importer les modules
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from bioforce_scraper.faq_scraper import FAQScraper
from bioforce_scraper.main import BioforceScraperMain
from bioforce_scraper.config import LOG_DIR

async def main():
    """Fonction principale pour exécuter le scraper"""
    parser = argparse.ArgumentParser(description='Exécuter le scraper Bioforce')
    parser.add_argument('--faq-only', action='store_true', help='Scraper uniquement la FAQ')
    parser.add_argument('--full', action='store_true', help='Scraper le site complet')
    args = parser.parse_args()
    
    # Par défaut, exécuter uniquement le scraper FAQ
    if not args.full and not args.faq_only:
        args.faq_only = True
    
    # Configurer le fichier de log spécifique à cette exécution
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    os.makedirs(LOG_DIR, exist_ok=True)
    
    # Exécuter le scraper demandé
    if args.faq_only:
        print("Démarrage du scraper de FAQ...")
        faq_scraper = FAQScraper()
        await faq_scraper.scrape_faq()
        print("Scraping de la FAQ terminé.")
    
    if args.full:
        print("Démarrage du scraper de site complet...")
        scraper = BioforceScraperMain()
        await scraper.run_scraper()
        print("Scraping du site complet terminé.")

if __name__ == "__main__":
    asyncio.run(main())
