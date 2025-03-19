"""
Script pour analyser la structure d'une page FAQ et extraire son contenu correctement
"""
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import os
import json
from pprint import pprint

# Liste des URLs à analyser
FAQ_URLS = [
    "https://www.bioforce.org/question/quelle-est-la-specificite-des-formations-bioforce/",
    "https://www.bioforce.org/question/quest-ce-que-biomoodle/"
]

async def analyze_faq_structure(url):
    """Analyse la structure d'une page FAQ et extrait son contenu"""
    print(f"\n=== Analyse de {url} ===")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                print(f"Erreur {response.status}")
                return
            
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')
            
            # Trouver le titre (question)
            print("\n--- TITRE ---")
            h1_tags = soup.find_all('h1')
            for i, h1 in enumerate(h1_tags):
                print(f"H1 #{i+1}: {h1.get_text().strip()}")
                print(f"Classes: {h1.get('class', [])}")
            
            # Chercher la div principale du contenu
            print("\n--- CONTENU ---")
            
            # Approche 1: Recherche par classe
            content_divs = soup.find_all('div', class_='question-content')
            print(f"Divs avec classe 'question-content': {len(content_divs)}")
            
            content_divs = soup.find_all('div', class_='answer-content')
            print(f"Divs avec classe 'answer-content': {len(content_divs)}")
            
            entry_divs = soup.find_all('div', class_='entry-content')
            print(f"Divs avec classe 'entry-content': {len(entry_divs)}")
            
            # Approche 2: Navigation par structure
            print("\n--- STRUCTURE ---")
            main_content = soup.find('div', class_='site-content')
            if main_content:
                content_structure = []
                for element in main_content.find_all(['div', 'article'], recursive=False):
                    class_names = element.get('class', [])
                    content_structure.append(f"- {element.name} (classes: {' '.join(class_names)})")
                    
                    # Niveau 2
                    for child in element.find_all(['div', 'section'], recursive=False):
                        child_classes = child.get('class', [])
                        content_structure.append(f"  - {child.name} (classes: {' '.join(child_classes)})")
                
                print("\n".join(content_structure))
            
            # Approche 3: Recherche spécifique pour DwQ (Div with Question)
            print("\n--- STRUCTURE SPÉCIFIQUE DwQ ---")
            dwqa_elements = soup.find_all(lambda tag: tag.name == 'div' and 'dwqa' in ' '.join(tag.get('class', [])))
            print(f"Éléments DWQA trouvés: {len(dwqa_elements)}")
            
            if dwqa_elements:
                # Analyser le premier élément DWQA
                dwqa = dwqa_elements[0]
                print(f"Classes DWQA: {dwqa.get('class', [])}")
                
                # Trouver la réponse
                answer = dwqa.find('div', class_='dwqa-answer-content')
                if answer:
                    print("\nCONTENU DE LA RÉPONSE:")
                    answer_text = answer.get_text().strip()
                    print(answer_text[:200] + "..." if len(answer_text) > 200 else answer_text)
                    
                    # Extraire tous les paragraphes
                    paragraphs = answer.find_all(['p', 'ul', 'ol', 'li', 'h2', 'h3', 'h4'])
                    print(f"\nNombre de paragraphes: {len(paragraphs)}")
                    for i, p in enumerate(paragraphs[:3]):
                        print(f"P#{i+1}: {p.get_text().strip()[:100]}...")
                else:
                    print("Aucun élément de réponse trouvé avec la classe 'dwqa-answer-content'")

async def main():
    for url in FAQ_URLS:
        await analyze_faq_structure(url)

if __name__ == "__main__":
    asyncio.run(main())
