"""
Script d'analyse de la structure HTML des pages FAQ pour déterminer les sélecteurs optimaux
Version 2 - Amélioration du formatage de sortie et analyses spécifiques
"""
import asyncio
import json
from playwright.async_api import async_playwright

# URL principale de la FAQ
FAQ_URL = "https://www.bioforce.org/faq/"

async def analyze_faq_structure():
    """Analyse la structure DOM de la page FAQ et identifie les sélecteurs optimaux"""
    print(f"\n{'='*80}")
    print(f"ANALYSE DE LA STRUCTURE HTML: {FAQ_URL}")
    print(f"{'='*80}\n")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        try:
            await page.goto(FAQ_URL, wait_until="networkidle", timeout=60000)
            print("✅ Page chargée avec succès")
        except Exception as e:
            print(f"❌ Erreur lors du chargement de la page: {e}")
            await browser.close()
            return
        
        # 1. Obtenir des informations sur l'accordéon
        accordion_info = await page.evaluate("""
            () => {
                // Chercher les accordéons 
                const accordions = document.querySelectorAll('.accordion');
                if (!accordions || accordions.length === 0) {
                    return { exists: false };
                }
                
                const firstAccordion = accordions[0];
                const items = firstAccordion.querySelectorAll('.accordion-item');
                
                const firstItem = items[0];
                let headerElement, bodyElement, questionText, answerText;
                
                if (firstItem) {
                    headerElement = firstItem.querySelector('.accordion-header');
                    bodyElement = firstItem.querySelector('.accordion-body');
                    
                    if (headerElement) {
                        questionText = headerElement.textContent.trim();
                    }
                    
                    if (bodyElement) {
                        answerText = bodyElement.textContent.trim().substring(0, 150) + '...';
                    }
                }
                
                return {
                    exists: true,
                    count: accordions.length,
                    itemCount: items.length,
                    structure: {
                        accordionClass: firstAccordion.className,
                        itemClass: firstItem ? firstItem.className : null,
                        headerClass: headerElement ? headerElement.className : null,
                        bodyClass: bodyElement ? bodyElement.className : null
                    },
                    example: {
                        question: questionText,
                        answer: answerText
                    }
                };
            }
        """)
        
        print("\n📋 STRUCTURE DES ACCORDÉONS")
        if accordion_info.get('exists', False):
            print(f"✅ {accordion_info['count']} accordéons trouvés avec {accordion_info['itemCount']} éléments")
            print("\nStructure:")
            print(f"- Classe accordéon: .{accordion_info['structure']['accordionClass'].replace(' ', '.')}")
            print(f"- Classe élément: .{accordion_info['structure']['itemClass'].replace(' ', '.')}")
            print(f"- Classe en-tête: .{accordion_info['structure']['headerClass'].replace(' ', '.')}")
            print(f"- Classe corps: .{accordion_info['structure']['bodyClass'].replace(' ', '.')}")
            
            print("\nExemple de contenu:")
            print(f"- Question: \"{accordion_info['example']['question']}\"")
            print(f"- Réponse: \"{accordion_info['example']['answer']}\"")
        else:
            print("❌ Aucun accordéon trouvé avec le sélecteur '.accordion'")
        
        # 2. Analyser les sélecteurs h4.title et div.desc
        h4_div_info = await page.evaluate("""
            () => {
                // Rechercher les h4 et div par classe
                const h4Elements = {
                    'h4.title': document.querySelectorAll('h4.title'),
                    'h4.faq-title': document.querySelectorAll('h4.faq-title'),
                    'h4[class*="faq"]': document.querySelectorAll('h4[class*="faq"]'),
                    'h4[class*="question"]': document.querySelectorAll('h4[class*="question"]'),
                    'h4': document.querySelectorAll('h4')
                };
                
                const divElements = {
                    'div.desc': document.querySelectorAll('div.desc'),
                    'div.description': document.querySelectorAll('div.description'),
                    'div[class*="faq"]': document.querySelectorAll('div[class*="faq"]'),
                    'div[class*="answer"]': document.querySelectorAll('div[class*="answer"]'),
                    'div[class*="content"]': document.querySelectorAll('div[class*="content"]')
                };
                
                // Collecter les résultats
                const h4Results = {};
                for (const [selector, elements] of Object.entries(h4Elements)) {
                    h4Results[selector] = {
                        count: elements.length,
                        example: elements.length > 0 ? elements[0].textContent.trim() : null,
                        classes: elements.length > 0 ? Array.from(elements[0].classList) : []
                    };
                }
                
                const divResults = {};
                for (const [selector, elements] of Object.entries(divElements)) {
                    divResults[selector] = {
                        count: elements.length,
                        example: elements.length > 0 ? elements[0].textContent.trim().substring(0, 150) + '...' : null,
                        classes: elements.length > 0 ? Array.from(elements[0].classList) : []
                    };
                }
                
                return { h4Results, divResults };
            }
        """)
        
        print("\n\n📋 ANALYSE DES SÉLECTEURS h4 ET div")
        
        print("\nSélecteurs h4:")
        for selector, info in h4_div_info['h4Results'].items():
            status = "✅" if info['count'] > 0 else "❌"
            print(f"{status} {selector}: {info['count']} éléments trouvés")
            if info['count'] > 0:
                print(f"   - Classes: {', '.join(info['classes'])}")
                print(f"   - Exemple: \"{info['example']}\"")
        
        print("\nSélecteurs div:")
        for selector, info in h4_div_info['divResults'].items():
            status = "✅" if info['count'] > 0 else "❌"
            print(f"{status} {selector}: {info['count']} éléments trouvés")
            if info['count'] > 0:
                print(f"   - Classes: {', '.join(info['classes'])}")
                print(f"   - Exemple: \"{info['example']}\"")
        
        # 3. Détecter les structures alternatives pour les questions/réponses
        alt_structure = await page.evaluate("""
            () => {
                // Approche basée sur du texto pour identifier les questions/réponses
                function isQuestion(text) {
                    if (!text) return false;
                    text = text.toLowerCase().trim();
                    return text.endsWith('?') || 
                           text.includes('comment') || 
                           text.includes('quand') || 
                           text.includes('pourquoi') || 
                           text.includes('puis-je') ||
                           text.includes('est-ce que');
                }
                
                const potentialQuestions = [];
                const questionContainers = [];
                
                // Chercher tous les éléments avec du texte
                document.querySelectorAll('h1, h2, h3, h4, h5, h6, p, div').forEach(el => {
                    const text = el.textContent.trim();
                    if (text.length > 10 && text.length < 200) {
                        if (isQuestion(text)) {
                            potentialQuestions.push({
                                element: el.tagName.toLowerCase(),
                                class: el.className,
                                text: text
                            });
                            
                            // Trouver l'élément parent qui pourrait contenir Q+R
                            let parent = el.parentElement;
                            if (parent && parent.children.length >= 2) {
                                questionContainers.push({
                                    container: parent.tagName.toLowerCase() + '.' + parent.className.replace(/ /g, '.'),
                                    questionEl: el.tagName.toLowerCase() + (el.className ? '.' + el.className.replace(/ /g, '.') : ''),
                                    answerEl: Array.from(parent.children)
                                                .filter(child => child !== el && child.textContent.trim().length > 20)
                                                .map(child => child.tagName.toLowerCase() + (child.className ? '.' + child.className.replace(/ /g, '.') : ''))
                                                .join(', ')
                                });
                            }
                        }
                    }
                });
                
                // Détecter les structures courantes basées sur les patterns identifiés
                const patterns = {};
                questionContainers.forEach(container => {
                    const key = container.questionEl + ' & ' + container.answerEl;
                    patterns[key] = (patterns[key] || 0) + 1;
                });
                
                // Trier les patterns par fréquence
                const sortedPatterns = Object.entries(patterns)
                    .sort((a, b) => b[1] - a[1])
                    .slice(0, 5)
                    .map(([pattern, count]) => ({ pattern, count }));
                
                return {
                    questionCount: potentialQuestions.length,
                    examples: potentialQuestions.slice(0, 5),
                    patterns: sortedPatterns,
                    containers: questionContainers.slice(0, 5)
                };
            }
        """)
        
        print("\n\n📋 STRUCTURES ALTERNATIVES DE QUESTIONS/RÉPONSES")
        print(f"Nombre de questions potentielles: {alt_structure['questionCount']}")
        
        print("\nExemples de questions:")
        for i, example in enumerate(alt_structure['examples']):
            print(f"{i+1}. <{example['element']}> \"{example['text']}\"")
        
        print("\nPatterns de structure Question/Réponse les plus fréquents:")
        for i, pattern in enumerate(alt_structure['patterns']):
            print(f"{i+1}. {pattern['pattern']} ({pattern['count']} occurrences)")
        
        print("\nExemples de containers Q/R:")
        for i, container in enumerate(alt_structure['containers']):
            print(f"{i+1}. Container: {container['container']}")
            print(f"   - Question: {container['questionEl']}")
            print(f"   - Réponse: {container['answerEl']}")
            
        # 4. Génération de sélecteurs optimisés
        print("\n\n🎯 RECOMMANDATIONS DE SÉLECTEURS")
        print("Basé sur l'analyse de la structure de la page, voici les sélecteurs recommandés:")
        
        # Priorité aux structures d'accordéon
        if accordion_info.get('exists', False):
            print("\n1. Priorité: Structure d'accordéon")
            print(f"   - Accordéon: .{accordion_info['structure']['accordionClass'].replace(' ', '.')}")
            print(f"   - Item: .{accordion_info['structure']['itemClass'].replace(' ', '.')}")
            print(f"   - Question: .{accordion_info['structure']['headerClass'].replace(' ', '.')}")
            print(f"   - Réponse: .{accordion_info['structure']['bodyClass'].replace(' ', '.')}")
            print("\n   Code recommandé pour extract_faq_items:")
            print("""
   ```javascript
   document.querySelectorAll('.accordion').forEach((accordion, index) => {
       // Trouver le titre de la catégorie (élément précédent)
       let title = "Catégorie " + (index + 1);
       let prevElement = accordion.previousElementSibling;
       if (prevElement && ['H2', 'H3', 'H4'].includes(prevElement.tagName)) {
           title = prevElement.textContent.trim();
       }
       
       // Extraire les éléments
       const items = [];
       accordion.querySelectorAll('.accordion-item').forEach(item => {
           const questionEl = item.querySelector('.accordion-header');
           const answerEl = item.querySelector('.accordion-body');
           
           if (questionEl && answerEl) {
               items.push({
                   question: questionEl.textContent.trim(),
                   answer: answerEl.textContent.trim(),
                   answer_html: answerEl.innerHTML
               });
           }
       });
       
       // Ajouter la catégorie
       categories.push({
           title: title,
           items: items
       });
   });
   ```""")
        else:
            # Utiliser les patterns alternatifs détectés
            print("\n1. Approche recommandée: Basée sur les patterns identifiés")
            if alt_structure['patterns'] and len(alt_structure['patterns']) > 0:
                pattern = alt_structure['patterns'][0]['pattern']
                parts = pattern.split(' & ')
                question_selector = parts[0]
                answer_selector = parts[1] if len(parts) > 1 else "nextElementSibling"
                
                print(f"   - Pattern principal: {pattern}")
                print(f"   - Sélecteur de question: {question_selector}")
                print(f"   - Sélecteur de réponse: {answer_selector}")
                
                print("\n   Code recommandé pour extract_faq_items:")
                print(f"""
   ```javascript
   // Trouver tous les éléments de question
   document.querySelectorAll('{question_selector}').forEach((questionEl, index) => {{
       // Déterminer la catégorie (peut être un élément parent ou précédent)
       let categoryEl = questionEl.closest('section, article, div[class*="category"]');
       let title = "Catégorie " + (index + 1);
       
       // Essayer de trouver un titre pour la catégorie
       let categoryTitle = categoryEl ? categoryEl.querySelector('h2, h3, h4') : null;
       if (categoryTitle) {{
           title = categoryTitle.textContent.trim();
       }}
       
       // Trouver l'élément de réponse associé
       let answerEl;
       if ('{answer_selector}' === 'nextElementSibling') {{
           answerEl = questionEl.nextElementSibling;
       }} else {{
           answerEl = questionEl.closest('div, section').querySelector('{answer_selector}');
       }}
       
       if (answerEl) {{
           items.push({{
               question: questionEl.textContent.trim(),
               answer: answerEl.textContent.trim(),
               answer_html: answerEl.innerHTML
           }});
       }}
   }});
   ```""")
            else:
                print("Aucun pattern clair n'a été identifié. Recommandation générique:")
                print("""
   ```javascript
   // Chercher les paires de questions/réponses basées sur le HTML
   document.querySelectorAll('h3, h4, h5').forEach((el) => {
       if (el.textContent.trim().endsWith('?')) {
           const nextEl = el.nextElementSibling;
           if (nextEl && ['P', 'DIV'].includes(nextEl.tagName)) {
               items.push({
                   question: el.textContent.trim(),
                   answer: nextEl.textContent.trim(),
                   answer_html: nextEl.innerHTML
               });
           }
       }
   });
   ```""")
        
        print("\n2. Sélecteurs alternatifs (fallback):")
        print("   Questions:")
        for selector, info in h4_div_info['h4Results'].items():
            if info['count'] > 0:
                print(f"   - {selector}")
        print("   Réponses:")
        for selector, info in h4_div_info['divResults'].items():
            if info['count'] > 0:
                print(f"   - {selector}")
                
        await browser.close()

async def main():
    await analyze_faq_structure()

if __name__ == "__main__":
    asyncio.run(main())
