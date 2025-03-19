"""
Script de test comparant différentes approches de scraping pour la FAQ Bioforce
"""
import asyncio
import json
from datetime import datetime
from typing import Dict, List, Any

from playwright.async_api import async_playwright, Page

# Configuration (repris du projet principal)
FAQ_URL = "https://www.bioforce.org/faq/"
FAQ_EN_URL = "https://www.bioforce.org/en/faq/"
FAQ_DETAIL_URL = "https://www.bioforce.org/question/comment-candidater-formation-bioforce/"

async def test_scraping_approaches(url: str):
    """
    Teste différentes approches de scraping sur une URL donnée
    et compare les résultats obtenus.
    """
    print(f"\n{'='*80}")
    print(f"TEST DE SCRAPING SUR: {url}")
    print(f"{'='*80}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        try:
            print("\n🌐 Chargement de la page...")
            await page.goto(url, wait_until="networkidle", timeout=60000)
            print("✅ Page chargée avec succès")
            
            # Test des deux approches
            results = {}
            
            # 1. Approche actuelle (accordéon)
            print("\n🧪 Test de l'approche actuelle (accordéon)...")
            current_approach_items = await extract_current_approach(page)
            results["current"] = {
                "count": len(current_approach_items),
                "items": current_approach_items[:3],  # Pour affichage, limite à 3 exemples
                "full_data": current_approach_items
            }
            
            # 2. Nouvelle approche (h4:title et div:desc)
            print("\n🧪 Test de la nouvelle approche (h4:title et div:desc)...")
            new_approach_items = await extract_new_approach(page)
            results["new"] = {
                "count": len(new_approach_items),
                "items": new_approach_items[:3],  # Pour affichage, limite à 3 exemples
                "full_data": new_approach_items
            }
            
            # Comparaison des résultats
            print_comparison(results)
            
            # Sauvegarder les résultats complets pour analyse
            save_results(url, results)
            
            return results
            
        except Exception as e:
            print(f"❌ Erreur: {str(e)}")
        finally:
            await browser.close()

async def extract_current_approach(page: Page) -> List[Dict[str, Any]]:
    """
    Extrait les éléments FAQ avec l'approche actuelle (accordéon).
    """
    categories = await page.evaluate("""
        () => {
            const categories = [];
            document.querySelectorAll('.accordion').forEach((accordion, index) => {
                // Trouver le titre de la catégorie (généralement un h2 ou h3 avant l'accordéon)
                let title = "Catégorie " + (index + 1);
                let prevElement = accordion.previousElementSibling;
                if (prevElement && ['H2', 'H3', 'H4'].includes(prevElement.tagName)) {
                    title = prevElement.textContent.trim();
                }
                
                // Extraire les éléments de l'accordéon
                const items = [];
                accordion.querySelectorAll('.accordion-item').forEach(item => {
                    const questionEl = item.querySelector('.accordion-header');
                    const answerEl = item.querySelector('.accordion-body');
                    
                    if (questionEl && answerEl) {
                        const question = questionEl.textContent.trim();
                        const answerHtml = answerEl.innerHTML;
                        const answerText = answerEl.textContent.trim();
                        
                        items.push({
                            question: question,
                            answer: answerText,
                            answer_html: answerHtml
                        });
                    }
                });
                
                categories.push({
                    title: title,
                    items: items
                });
            });
            return categories;
        }
    """)
    
    # Aplatir les catégories en une liste d'éléments FAQ
    faq_items = []
    for category in categories:
        category_title = category["title"]
        for item in category["items"]:
            faq_items.append({
                "category": category_title,
                "question": item["question"],
                "answer": item["answer"],
                "answer_html": item["answer_html"],
                "approach": "current"
            })
    
    print(f"✅ Approche actuelle: {len(faq_items)} éléments extraits")
    return faq_items

async def extract_new_approach(page: Page) -> List[Dict[str, Any]]:
    """
    Extrait les éléments FAQ avec la nouvelle approche (h4:title et div:desc).
    """
    categories = await page.evaluate("""
        () => {
            const categories = [];
            
            // Trouver tous les h4 potentiels (titres de section)
            document.querySelectorAll('h4.title, h4.faq-title, h4').forEach((titleEl, index) => {
                const title = titleEl.textContent.trim();
                const items = [];
                
                // Stratégie 1: Chercher les div.desc qui suivent
                let nextEl = titleEl.nextElementSibling;
                while (nextEl && nextEl.tagName !== 'H4') {
                    if (nextEl.matches('div.desc, div.description')) {
                        const question = nextEl.getAttribute('data-question') || 
                                        nextEl.querySelector('h5, strong')?.textContent.trim() || 
                                        `Question ${items.length + 1}`;
                                        
                        const answerEl = nextEl.querySelector('p') || nextEl;
                        
                        items.push({
                            question: question,
                            answer: answerEl.textContent.trim(),
                            answer_html: answerEl.innerHTML
                        });
                    }
                    nextEl = nextEl.nextElementSibling;
                }
                
                // Stratégie 2: Fallback sur structure d'accordéon si rien trouvé
                if (items.length === 0) {
                    const accordion = titleEl.nextElementSibling?.classList.contains('accordion') 
                        ? titleEl.nextElementSibling 
                        : document.querySelector('.accordion');
                        
                    if (accordion) {
                        accordion.querySelectorAll('.accordion-item').forEach(item => {
                            const questionEl = item.querySelector('.accordion-header, .card-header, [data-bs-toggle="collapse"]');
                            const answerEl = item.querySelector('.accordion-body, .card-body, .collapse');
                            
                            if (questionEl && answerEl) {
                                items.push({
                                    question: questionEl.textContent.trim(),
                                    answer: answerEl.textContent.trim(),
                                    answer_html: answerEl.innerHTML
                                });
                            }
                        });
                    }
                }
                
                if (items.length > 0) {
                    categories.push({
                        title: title,
                        items: items
                    });
                }
            });
            
            return categories;
        }
    """)
    
    # Aplatir les catégories en une liste d'éléments FAQ
    faq_items = []
    for category in categories:
        category_title = category["title"]
        for item in category["items"]:
            faq_items.append({
                "category": category_title,
                "question": item["question"],
                "answer": item["answer"],
                "answer_html": item["answer_html"],
                "approach": "new"
            })
    
    print(f"✅ Nouvelle approche: {len(faq_items)} éléments extraits")
    return faq_items

def print_comparison(results: Dict[str, Any]):
    """
    Affiche une comparaison des résultats des deux approches.
    """
    current_count = results["current"]["count"]
    new_count = results["new"]["count"]
    
    print("\n" + "="*80)
    print("COMPARAISON DES RÉSULTATS")
    print("="*80)
    
    print("\n📊 STATISTIQUES:")
    print(f"- Approche actuelle (accordéon): {current_count} éléments")
    print(f"- Nouvelle approche (h4:title/div:desc): {new_count} éléments")
    
    if current_count > 0 and new_count > 0:
        difference = ((new_count - current_count) / current_count) * 100
        status = "✅" if new_count >= current_count else "⚠️"
        print(f"{status} Différence: {difference:.1f}% ({new_count - current_count} éléments)")
    
    # Comparer le contenu
    print("\n📋 EXEMPLES DE CONTENU:")
    
    print("\nApproche actuelle (accordéon):")
    for i, item in enumerate(results["current"]["items"]):
        print(f"{i+1}. Catégorie: {item['category']}")
        print(f"   Question: {item['question'][:80]}...")
        print(f"   Réponse: {item['answer'][:80]}...")
        print()
    
    print("\nNouvelle approche (h4:title/div:desc):")
    for i, item in enumerate(results["new"]["items"]):
        print(f"{i+1}. Catégorie: {item['category']}")
        print(f"   Question: {item['question'][:80]}...")
        print(f"   Réponse: {item['answer'][:80]}...")
        print()
    
    # Analyse de chevauchement
    current_questions = set([item["question"] for item in results["current"]["full_data"]])
    new_questions = set([item["question"] for item in results["new"]["full_data"]])
    
    common_questions = current_questions.intersection(new_questions)
    only_current = current_questions - new_questions
    only_new = new_questions - current_questions
    
    print("\n🔄 ANALYSE DE CHEVAUCHEMENT:")
    print(f"- Questions communes aux deux approches: {len(common_questions)}")
    print(f"- Questions uniquement dans l'approche actuelle: {len(only_current)}")
    print(f"- Questions uniquement dans la nouvelle approche: {len(only_new)}")
    
    if len(only_current) > 0:
        print("\nExemples de questions uniquement dans l'approche actuelle:")
        for q in list(only_current)[:3]:
            print(f"- {q[:80]}...")
    
    if len(only_new) > 0:
        print("\nExemples de questions uniquement dans la nouvelle approche:")
        for q in list(only_new)[:3]:
            print(f"- {q[:80]}...")

def save_results(url: str, results: Dict[str, Any]):
    """
    Sauvegarde les résultats complets dans un fichier JSON pour analyse.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"faq_scraping_test_{timestamp}.json"
    
    data = {
        "url": url,
        "timestamp": timestamp,
        "current_approach": {
            "count": results["current"]["count"],
            "items": results["current"]["full_data"]
        },
        "new_approach": {
            "count": results["new"]["count"],
            "items": results["new"]["full_data"]
        }
    }
    
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Résultats complets sauvegardés dans: {filename}")

async def main():
    """
    Fonction principale exécutant les tests sur différentes URLs.
    """
    print("🧪 TEST DES APPROCHES DE SCRAPING FAQ BIOFORCE")
    print("="*80)
    
    # Tester sur la page FAQ principale
    await test_scraping_approaches(FAQ_URL)
    
    # Tester sur la version anglaise
    await test_scraping_approaches(FAQ_EN_URL)
    
    # Tester sur une page de détail
    await test_scraping_approaches(FAQ_DETAIL_URL)

if __name__ == "__main__":
    asyncio.run(main())
