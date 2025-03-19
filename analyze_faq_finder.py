"""
Script d'analyse pour identifier la structure correcte des pages FAQ et extraire les URLs
"""
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
from pprint import pprint

# URL de base pour les FAQ Bioforce
FAQ_BASE_URL = "https://www.bioforce.org/foire-aux-questions/"

async def analyze_faq_page(url):
    """Analyse une page de FAQ et affiche sa structure"""
    print(f"\n=== Analyse de la page FAQ: {url} ===")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                print(f"Erreur {response.status} lors de l'accès à {url}")
                return []
            
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')
            
            # Afficher les éléments principaux
            print("\n=== Structure principale de la page ===")
            main_divs = soup.select('main, div.site-content, div.content-area, div.page-content')
            for i, div in enumerate(main_divs):
                print(f"Élément principal #{i+1}: {div.name}.{' '.join(div.get('class', []))}")
            
            # Afficher tous les liens
            print("\n=== Liens trouvés sur la page ===")
            all_links = {}
            for a in soup.find_all('a', href=True):
                href = a.get('href', '').strip()
                if not href or href.startswith('#'):
                    continue
                
                text = a.get_text().strip()
                # Grouper les liens par texte
                if text in all_links:
                    all_links[text].append(href)
                else:
                    all_links[text] = [href]
            
            # Afficher les liens regroupés
            for text, hrefs in all_links.items():
                if len(text) > 50:
                    text = text[:50] + "..."
                if len(hrefs) == 1:
                    print(f"• {text}: {hrefs[0]}")
                else:
                    print(f"• {text}: {len(hrefs)} liens")
            
            # Rechercher spécifiquement les liens des questions FAQ
            faq_links = []
            faq_patterns = [
                '/question/', 
                '/faq/', 
                '/foire-aux-questions/'
            ]
            
            for a in soup.find_all('a', href=True):
                href = a.get('href', '').strip()
                if not href:
                    continue
                
                # Vérifier si c'est un lien de question
                for pattern in faq_patterns:
                    if pattern in href:
                        # Convertir en URL absolue si nécessaire
                        absolute_url = urljoin(url, href)
                        faq_links.append({
                            'url': absolute_url,
                            'text': a.get_text().strip() or 'Pas de texte'
                        })
                        break
            
            # Afficher les liens FAQ trouvés
            print(f"\n=== {len(faq_links)} Liens FAQ trouvés ===")
            for i, link in enumerate(faq_links[:10]):  # Limiter à 10 pour l'affichage
                print(f"{i+1}. {link['text']}: {link['url']}")
            
            if len(faq_links) > 10:
                print(f"... et {len(faq_links) - 10} autres")
            
            # Retourner les URLs des FAQ trouvées
            return [link['url'] for link in faq_links]

async def main():
    """Fonction principale"""
    print(f"Analyse de la page principale de FAQ")
    
    # Analyser la page principale des FAQ
    faq_urls = await analyze_faq_page(FAQ_BASE_URL)
    print(f"\nTotal des URLs FAQ trouvées: {len(faq_urls)}")
    
    # Si des catégories de FAQ sont trouvées, les analyser aussi
    if faq_urls:
        print("\nAnalyse des premières catégories de FAQ...")
        for url in faq_urls[:3]:  # Limiter à 3 pour l'analyse initiale
            if '/foire-aux-questions/' in url and url != FAQ_BASE_URL:
                category_urls = await analyze_faq_page(url)
                print(f"Catégorie {url}: {len(category_urls)} questions trouvées")

if __name__ == "__main__":
    asyncio.run(main())
