import asyncio
from playwright.async_api import async_playwright

async def extract_h3_titles():
    """
    Extrait et affiche tous les éléments h3 de la page FAQ Bioforce
    """
    print("\n=== EXTRACTION DES ÉLÉMENTS h3 DE LA FAQ BIOFORCE ===\n")
    
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
            
            # Extraire tous les h3
            h3_elements = await page.evaluate("""() => {
                const h3s = document.querySelectorAll('h3');
                return Array.from(h3s).map((el, index) => {
                    // Vérifier s'il contient un span.subtile
                    const subtile = el.querySelector('span.subtile');
                    let subtileText = '';
                    if (subtile) {
                        subtileText = subtile.textContent.trim();
                    }
                    
                    // Obtenir le texte du h3 sans le span.subtile
                    let mainText = el.textContent.trim();
                    if (subtileText && mainText.includes(subtileText)) {
                        mainText = mainText.replace(subtileText, '').trim();
                    }
                    
                    // Trouver les h4.title qui suivent ce h3
                    const parentContainer = el.parentElement;
                    let relatedH4Count = 0;
                    let relatedH4Titles = [];
                    
                    if (parentContainer) {
                        const h4Titles = parentContainer.querySelectorAll('h4.title');
                        relatedH4Count = h4Titles.length;
                        
                        // Limiter à 3 titres pour l'aperçu
                        relatedH4Titles = Array.from(h4Titles)
                            .slice(0, 3)
                            .map(h4 => h4.textContent.trim());
                    }
                    
                    return {
                        index: index + 1,
                        fullText: el.textContent.trim(),
                        mainText: mainText,
                        hasSubtile: !!subtile,
                        subtileText: subtileText,
                        relatedH4Count: relatedH4Count,
                        relatedH4Preview: relatedH4Titles
                    };
                });
            }""")
            
            # Afficher les résultats
            print(f"\nNombre total d'éléments h3 trouvés: {len(h3_elements)}\n")
            print("Liste des h3:")
            print("===========\n")
            
            for item in h3_elements:
                print(f"{item['index']}. {item['fullText']}")
                
                if item['hasSubtile']:
                    print(f"   ├── Sous-titre: {item['subtileText']}")
                    print(f"   └── Titre principal: {item['mainText']}")
                
                print(f"   └── Questions associées: {item['relatedH4Count']}")
                
                if item['relatedH4Preview'] and len(item['relatedH4Preview']) > 0:
                    print("       Aperçu des questions:")
                    for i, q in enumerate(item['relatedH4Preview']):
                        print(f"       {i+1}. {q}")
                
                print("")
            
            # Sauvegarder la liste dans un fichier texte
            with open("liste_h3.txt", "w", encoding="utf-8") as f:
                f.write(f"Nombre total d'éléments h3 trouvés: {len(h3_elements)}\n\n")
                
                for item in h3_elements:
                    f.write(f"=== H3 #{item['index']} ===\n")
                    f.write(f"Texte complet: {item['fullText']}\n")
                    
                    if item['hasSubtile']:
                        f.write(f"Sous-titre: {item['subtileText']}\n")
                        f.write(f"Titre principal: {item['mainText']}\n")
                    
                    f.write(f"Nombre de questions associées: {item['relatedH4Count']}\n")
                    
                    if item['relatedH4Preview'] and len(item['relatedH4Preview']) > 0:
                        f.write("Aperçu des questions:\n")
                        for i, q in enumerate(item['relatedH4Preview']):
                            f.write(f"  {i+1}. {q}\n")
                    
                    f.write("\n-----------------------------------\n\n")
            
            print(f"\nListe sauvegardée dans le fichier liste_h3.txt")
            
        except Exception as e:
            print(f"Erreur lors de l'extraction: {str(e)}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(extract_h3_titles())