import asyncio
from playwright.async_api import async_playwright
import re

async def extract_div_desc():
    """
    Extrait et affiche tous les éléments div.desc de la page FAQ Bioforce
    """
    print("\n=== EXTRACTION DES ÉLÉMENTS div.desc DE LA FAQ BIOFORCE ===\n")
    
    async with async_playwright() as p:
        # Lancer le navigateur Firefox
        browser = await p.firefox.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        
        try:
            # Accéder à la page FAQ
            print("Chargement de la page FAQ Bioforce...")
            await page.goto("https://www.bioforce.org/faq/", wait_until="domcontentloaded")
            await page.wait_for_load_state("networkidle")
            
            # Auto-scroll pour charger tout le contenu dynamique
            print("Auto-scroll pour charger tout le contenu...")
            await page.evaluate("""async () => {
                await new Promise(resolve => {
                    let totalHeight = 0;
                    const distance = 100;
                    const timer = setInterval(() => {
                        const scrollHeight = document.body.scrollHeight;
                        window.scrollBy(0, distance);
                        totalHeight += distance;
                        
                        if (totalHeight >= scrollHeight){
                            clearInterval(timer);
                            resolve();
                        }
                    }, 100);
                });
            }""")
            
            # Extraire tous les div.desc
            div_descs = await page.evaluate("""() => {
                const descElements = document.querySelectorAll('div.desc');
                return Array.from(descElements).map((el, index) => {
                    const paragraphs = el.querySelectorAll('p');
                    let paragraphTexts = [];
                    
                    if (paragraphs.length > 0) {
                        paragraphTexts = Array.from(paragraphs).map(p => p.textContent.trim());
                    }
                    
                    // Obtenir l'élément précédent pour voir s'il est lié à un h4.title
                    let previousElement = el.previousElementSibling;
                    let previousIsTitle = false;
                    let previousText = '';
                    
                    if (previousElement) {
                        previousIsTitle = previousElement.tagName === 'H4' && 
                                         previousElement.classList.contains('title');
                        previousText = previousElement.textContent.trim();
                    }
                    
                    return {
                        index: index + 1,
                        text: el.textContent.trim(),
                        textLength: el.textContent.trim().length,
                        hasParagraphs: paragraphs.length > 0,
                        paragraphCount: paragraphs.length,
                        paragraphTexts: paragraphTexts,
                        previousIsTitle: previousIsTitle,
                        previousText: previousText
                    };
                });
            }""")
            
            # Afficher les résultats
            print(f"\nNombre total d'éléments div.desc trouvés: {len(div_descs)}\n")
            print("Résumé des div.desc:")
            print("==================\n")
            
            for item in div_descs:
                # Limiter la longueur du texte pour l'affichage
                text_preview = item['text'][:100] + "..." if len(item['text']) > 100 else item['text']
                text_preview = re.sub(r'\s+', ' ', text_preview).strip()
                
                print(f"{item['index']}. Longueur: {item['textLength']} caractères")
                print(f"   Aperçu: {text_preview}")
                print(f"   Nombre de paragraphes: {item['paragraphCount']}")
                
                if item['previousIsTitle']:
                    print(f"   Question associée: {item['previousText']}")
                
                print("")
            
            # Sauvegarder les données complètes dans un fichier texte
            with open("liste_div_desc.txt", "w", encoding="utf-8") as f:
                f.write(f"Nombre total d'éléments div.desc trouvés: {len(div_descs)}\n\n")
                
                for item in div_descs:
                    f.write(f"=== DIV.DESC #{item['index']} ===\n")
                    
                    if item['previousIsTitle']:
                        f.write(f"Question associée: {item['previousText']}\n\n")
                    
                    f.write(f"Texte complet ({item['textLength']} caractères):\n")
                    f.write(f"{item['text']}\n\n")
                    
                    if item['hasParagraphs']:
                        f.write(f"Contenu des {item['paragraphCount']} paragraphes:\n")
                        for i, p_text in enumerate(item['paragraphTexts']):
                            f.write(f"  P{i+1}: {p_text}\n")
                    
                    f.write("\n-----------------------------------\n\n")
            
            print(f"\nListe complète sauvegardée dans le fichier liste_div_desc.txt")
            
        except Exception as e:
            print(f"Erreur lors de l'extraction: {str(e)}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(extract_div_desc())