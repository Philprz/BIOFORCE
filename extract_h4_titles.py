import asyncio
from playwright.async_api import async_playwright

async def extract_h4_titles():
    """
    Extrait et affiche tous les éléments h4.title de la page FAQ Bioforce
    """
    print("\n=== EXTRACTION DES ÉLÉMENTS h4.title DE LA FAQ BIOFORCE ===\n")
    
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
            
            # Extraire tous les textes des h4.title
            h4_titles = await page.evaluate("""() => {
                const h4Elements = document.querySelectorAll('h4.title');
                return Array.from(h4Elements).map((el, index) => {
                    return {
                        index: index + 1,
                        text: el.textContent.trim()
                    };
                });
            }""")
            
            # Afficher les résultats
            print(f"\nNombre total d'éléments h4.title trouvés: {len(h4_titles)}\n")
            print("Liste complète des h4.title:")
            print("==========================\n")
            
            for item in h4_titles:
                print(f"{item['index']}. {item['text']}")
            
            # Sauvegarder la liste dans un fichier texte
            with open("liste_h4_titles.txt", "w", encoding="utf-8") as f:
                for item in h4_titles:
                    f.write(f"{item['index']}. {item['text']}\n")
            
            print(f"\nListe sauvegardée dans le fichier liste_h4_titles.txt")
            
        except Exception as e:
            print(f"Erreur lors de l'extraction: {str(e)}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(extract_h4_titles())