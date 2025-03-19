"""
Script d'analyse de la structure HTML des pages FAQ pour déterminer les sélecteurs optimaux
"""
import asyncio
from playwright.async_api import async_playwright

# URLs de la FAQ
FAQ_URLS = [
    "https://www.bioforce.org/faq/",
    "https://www.bioforce.org/en/faq/",
    "https://www.bioforce.org/question/",
    "https://www.bioforce.org/en/question/"
]

async def analyze_page_structure(url):
    """Analyse la structure DOM de la page et identifie les sélecteurs optimaux"""
    print(f"\n\n{'='*80}\nAnalyse de {url}\n{'='*80}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        # Navigation vers la page
        try:
            await page.goto(url, wait_until="networkidle", timeout=60000)
            print("✅ Page chargée avec succès")
        except Exception as e:
            print(f"❌ Erreur lors du chargement de la page: {e}")
            await browser.close()
            return
        
        # 1. Analyse générale de la structure
        structure = await page.evaluate("""
            () => {
                // Fonction pour obtenir un chemin simplifié d'un élément
                function getSimplePath(element) {
                    if (!element) return '';
                    
                    let path = element.tagName.toLowerCase();
                    if (element.id) path += '#' + element.id;
                    if (element.className) {
                        const classes = Array.from(element.classList).join('.');
                        if (classes) path += '.' + classes;
                    }
                    return path;
                }
                
                // Analyser la structure de la FAQ
                const structure = {
                    title: {
                        selectors: [],
                        samples: []
                    },
                    questions: {
                        selectors: [],
                        samples: []
                    },
                    answers: {
                        selectors: [],
                        samples: []
                    }
                };
                
                // Recherche de questions typiques pour identifier la structure
                const questionKeywords = ['comment', 'quand', 'pourquoi', 'est-ce que', 'quelles', 'puis-je'];
                document.querySelectorAll('h1, h2, h3, h4, h5, h6, p, div').forEach(el => {
                    const text = el.textContent.trim().toLowerCase();
                    
                    if (text.length > 10 && text.length < 150) {
                        // Détecter les titres de section FAQ
                        if (text.includes('faq') || text.includes('question') || text.includes('foire aux questions')) {
                            structure.title.selectors.push(getSimplePath(el));
                            structure.title.samples.push({
                                text: el.textContent.trim(),
                                path: getSimplePath(el)
                            });
                        }
                        
                        // Détecter les questions
                        if (text.endsWith('?') || questionKeywords.some(kw => text.includes(kw))) {
                            structure.questions.selectors.push(getSimplePath(el));
                            structure.questions.samples.push({
                                text: el.textContent.trim(),
                                path: getSimplePath(el)
                            });
                        }
                    }
                    
                    // Détecter les réponses (généralement des paragraphes proches des questions)
                    if (text.length > 30 && el.tagName.toLowerCase() === 'p') {
                        structure.answers.selectors.push(getSimplePath(el));
                        structure.answers.samples.push({
                            text: el.textContent.trim().substring(0, 100) + '...',
                            path: getSimplePath(el)
                        });
                    }
                });
                
                // Compter et trier les sélecteurs les plus fréquents
                function countSelectors(selectors) {
                    const counts = {};
                    selectors.forEach(s => {
                        counts[s] = (counts[s] || 0) + 1;
                    });
                    return Object.entries(counts)
                        .sort((a, b) => b[1] - a[1])
                        .slice(0, 5)
                        .map(([selector, count]) => ({ selector, count }));
                }
                
                return {
                    url: window.location.href,
                    title: document.title,
                    commonSelectors: {
                        title: countSelectors(structure.title.selectors),
                        questions: countSelectors(structure.questions.selectors),
                        answers: countSelectors(structure.answers.selectors)
                    },
                    samples: {
                        title: structure.title.samples.slice(0, 3),
                        questions: structure.questions.samples.slice(0, 5),
                        answers: structure.answers.samples.slice(0, 5)
                    }
                };
            }
        """)
        
        print("\n📊 ANALYSE GÉNÉRALE DE LA STRUCTURE")
        print(f"Titre de la page: {structure['title']}")
        print(f"URL: {structure['url']}")
        
        print("\n🔍 SÉLECTEURS LES PLUS FRÉQUENTS")
        print("\nTitres de section FAQ:")
        for item in structure['commonSelectors']['title']:
            print(f"  - {item['selector']} ({item['count']} occurrences)")
            
        print("\nQuestions:")
        for item in structure['commonSelectors']['questions']:
            print(f"  - {item['selector']} ({item['count']} occurrences)")
            
        print("\nRéponses:")
        for item in structure['commonSelectors']['answers']:
            print(f"  - {item['selector']} ({item['count']} occurrences)")
        
        print("\n📝 EXEMPLES DE CONTENU")
        print("\nTitres de section:")
        for item in structure['samples']['title']:
            print(f"  - \"{item['text']}\" ({item['path']})")
            
        print("\nQuestions:")
        for item in structure['samples']['questions']:
            print(f"  - \"{item['text']}\" ({item['path']})")
            
        print("\nRéponses (début):")
        for item in structure['samples']['answers']:
            print(f"  - \"{item['text']}\" ({item['path']})")
        
        # 2. Analyse spécifique des structures d'accordéon
        accordion_structure = await page.evaluate("""
            () => {
                const accordions = document.querySelectorAll('.accordion, [data-toggle="collapse"], [data-bs-toggle="collapse"]');
                if (accordions.length === 0) return { found: false };
                
                return {
                    found: true,
                    count: accordions.length,
                    structure: Array.from(accordions).slice(0, 3).map(accordion => {
                        // Analyser la structure de l'accordéon
                        const items = accordion.querySelectorAll('.accordion-item, .card, .panel');
                        
                        return {
                            tag: accordion.tagName.toLowerCase(),
                            classes: Array.from(accordion.classList),
                            itemCount: items.length,
                            itemSample: items.length > 0 ? {
                                tag: items[0].tagName.toLowerCase(),
                                classes: Array.from(items[0].classList),
                                headerSelector: items[0].querySelector('.accordion-header, .card-header, .panel-heading')?.tagName.toLowerCase(),
                                bodySelector: items[0].querySelector('.accordion-body, .card-body, .panel-body')?.tagName.toLowerCase(),
                                questionText: items[0].querySelector('.accordion-header, .card-header, .panel-heading')?.textContent.trim(),
                                answerText: items[0].querySelector('.accordion-body, .card-body, .panel-body')?.textContent.trim().substring(0, 100) + '...'
                            } : null
                        };
                    })
                };
            }
        """)
        
        print("\n🪗 ANALYSE DES STRUCTURES D'ACCORDÉON")
        if accordion_structure['found']:
            print(f"Nombre d'accordéons trouvés: {accordion_structure['count']}")
            print("\nStructure des accordéons:")
            for i, acc in enumerate(accordion_structure['structure']):
                print(f"\nAccordéon #{i+1}:")
                print(f"  - Tag: {acc['tag']}")
                print(f"  - Classes: {', '.join(acc['classes'])}")
                print(f"  - Nombre d'items: {acc['itemCount']}")
                
                if acc['itemSample']:
                    print("  - Exemple d'item:")
                    print(f"    - Tag: {acc['itemSample']['tag']}")
                    print(f"    - Classes: {', '.join(acc['itemSample']['classes'])}")
                    print(f"    - En-tête: {acc['itemSample']['headerSelector']}")
                    print(f"    - Corps: {acc['itemSample']['bodySelector']}")
                    print(f"    - Question: \"{acc['itemSample']['questionText']}\"")
                    print(f"    - Réponse: \"{acc['itemSample']['answerText']}\"")
        else:
            print("Aucune structure d'accordéon trouvée sur cette page.")
            
        # 3. Analyse des h4:title et div:desc spécifiques
        target_structure = await page.evaluate("""
            () => {
                const h4Titles = document.querySelectorAll('h4.title, h4');
                const divDescs = document.querySelectorAll('div.desc, div.description');
                
                const h4Sample = h4Titles.length > 0 ? {
                    text: h4Titles[0].textContent.trim(),
                    html: h4Titles[0].outerHTML,
                    classes: Array.from(h4Titles[0].classList)
                } : null;
                
                const divDescSample = divDescs.length > 0 ? {
                    text: divDescs[0].textContent.trim().substring(0, 100) + '...',
                    html: divDescs[0].outerHTML.substring(0, 200) + '...',
                    classes: Array.from(divDescs[0].classList)
                } : null;
                
                // Essayer de trouver une relation entre h4 et divs
                let relationship = null;
                if (h4Titles.length > 0 && divDescs.length > 0) {
                    const h4First = h4Titles[0];
                    const siblings = Array.from(h4First.parentNode.children);
                    const h4Index = siblings.indexOf(h4First);
                    
                    // Vérifier si un div.desc suit directement un h4.title
                    if (h4Index >= 0 && h4Index < siblings.length - 1) {
                        const nextElement = siblings[h4Index + 1];
                        if (nextElement && nextElement.matches('div.desc, div.description')) {
                            relationship = {
                                pattern: 'adjacent-siblings',
                                example: {
                                    h4: h4First.textContent.trim(),
                                    div: nextElement.textContent.trim().substring(0, 100) + '...'
                                }
                            };
                        }
                    }
                }
                
                return {
                    h4Count: h4Titles.length,
                    divDescCount: divDescs.length,
                    h4Sample,
                    divDescSample,
                    relationship
                };
            }
        """)
        
        print("\n🎯 ANALYSE DES SÉLECTEURS CIBLES (h4:title et div:desc)")
        print(f"Nombre de h4.title trouvés: {target_structure['h4Count']}")
        print(f"Nombre de div.desc trouvés: {target_structure['divDescCount']}")
        
        if target_structure['h4Sample']:
            print("\nExemple de h4.title:")
            print(f"  - Texte: \"{target_structure['h4Sample']['text']}\"")
            print(f"  - Classes: {target_structure['h4Sample']['classes']}")
            print(f"  - HTML: {target_structure['h4Sample']['html']}")
        else:
            print("Aucun élément h4.title trouvé.")
            
        if target_structure['divDescSample']:
            print("\nExemple de div.desc:")
            print(f"  - Texte: \"{target_structure['divDescSample']['text']}\"")
            print(f"  - Classes: {target_structure['divDescSample']['classes']}")
            print(f"  - HTML: {target_structure['divDescSample']['html']}")
        else:
            print("Aucun élément div.desc trouvé.")
            
        if target_structure['relationship']:
            print("\nRelation entre h4.title et div.desc:")
            print(f"  - Pattern: {target_structure['relationship']['pattern']}")
            print("  - Exemple:")
            print(f"    - h4: \"{target_structure['relationship']['example']['h4']}\"")
            print(f"    - div: \"{target_structure['relationship']['example']['div']}\"")
        else:
            print("Aucune relation directe trouvée entre h4.title et div.desc.")
        
        # SECTION 4: Recherche d'identifiants spécifiques dans les questions
        identifiers_found = []
        print("\n🔍 Identifiants spécifiques dans les questions:", len(identifiers_found))
        # Afficher les résultats
        if identifiers_found:
            for identifier in identifiers_found:
                print(f"  - {identifier}")
        else:
            print("  - Aucun identifiant spécifique trouvé")
        
        await browser.close()

async def main():
    """Fonction principale"""
    print("🔍 ANALYSE DE LA STRUCTURE DES PAGES FAQ BIOFORCE")
    print("="*80)
    
    for url in FAQ_URLS:
        await analyze_page_structure(url)
    
    # Proposer des recommandations de sélecteurs
    print("\n\n📋 RECOMMANDATIONS DE SÉLECTEURS")
    print("="*80)
    print("""
Basé sur l'analyse effectuée, voici les recommandations de sélecteurs:

1. Pour les pages avec structure d'accordéon (courant dans les FAQ):
   - Questions: '.accordion-header, .card-header, h5.accordion-button'
   - Réponses: '.accordion-body, .card-body, .accordion-collapse'

2. Pour les pages avec structure h4/div:
   - Titres de section: 'h4.title, h4.faq-title, h4'
   - Description/Réponses: 'div.desc, div.description, div.faq-content'

3. Sélecteurs génériques (fallback):
   - Questions: 'h5:contains(?), p.question, .faq-question'
   - Réponses: 'p:not(.question), .faq-answer, div.answer'

Ces recommandations seront affinées après l'analyse des pages concrètes.
""")

if __name__ == "__main__":
    asyncio.run(main())
