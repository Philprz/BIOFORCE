# h3-h4.py

import asyncio
from playwright.async_api import async_playwright
import pandas as pd

async def scrape_titles_and_questions():
    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://www.bioforce.org/faq/", wait_until="domcontentloaded")

        # Scroll pour charger le contenu dynamique
        await page.evaluate("""async () => {
            await new Promise(resolve => {
                const distance = 100;
                const timer = setInterval(() => {
                    window.scrollBy(0, distance);
                    if (window.innerHeight + window.scrollY >= document.body.scrollHeight) {
                        clearInterval(timer);
                        resolve();
                    }
                }, 100);
            });
        }""")

        # Extraction des titres h3 et questions h4.title
        data = await page.evaluate("""() => {
            const h3_elements = Array.from(document.querySelectorAll('h3')).map(h3 => h3.innerText.trim());
            const h4_elements = Array.from(document.querySelectorAll('h4.title')).map(h4 => h4.innerText.trim());

            return { h3_elements, h4_elements };
        }""")

        await browser.close()

        # Affichage des résultats
        print(f"Nombre total de titres h3 : {len(data['h3_elements'])}")
        print(f"Nombre total de questions h4.title : {len(data['h4_elements'])}")

        # Sauvegarde en CSV
        df_h3 = pd.DataFrame(data['h3_elements'], columns=['Titre (h3)'])
        df_h4 = pd.DataFrame(data['h4_elements'], columns=['Question (h4.title)'])

        df_h3.to_csv("bioforce_h3.csv", index=False, encoding='utf-8')
        df_h4.to_csv("bioforce_h4_questions.csv", index=False, encoding='utf-8')

        print("Données enregistrées dans 'bioforce_h3.csv' et 'bioforce_h4_questions.csv'")

# Exécution
asyncio.run(scrape_titles_and_questions())
