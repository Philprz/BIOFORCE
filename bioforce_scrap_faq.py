import asyncio
import json
import re
import pandas as pd
from playwright.async_api import async_playwright
from datetime import datetime
import os

async def scrape_bioforce_faq_precise():
    """
    Scraper précis pour la FAQ Bioforce qui extrait correctement les titres 
    de la partie gauche du site et les associe aux questions correspondantes.
    Le résultat est formaté exactement comme faq.csv (Catégorie;Titre;Question;Réponse)
    """
    print("\n=== EXTRACTION PRÉCISE DE LA FAQ BIOFORCE FORMAT FAQ.CSV ===\n")
    
    all_faq_data = []
    sections_data = []
    
    async with async_playwright() as p:
        # Créer un dossier pour les captures d'écran de debug
        debug_dir = "debug_screenshots"
        os.makedirs(debug_dir, exist_ok=True)
        
        # Lancer le navigateur Chromium (au lieu de Firefox) qui pourrait être plus stable
        print("Lancement du navigateur Chromium...")
        browser = await p.chromium.launch(headless=False)  # Mode visible pour déboguer
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        
        try:
            # Accéder à la page FAQ de Bioforce
            print("Accès à la page FAQ de Bioforce...")
            await page.goto("https://bioforce.org/faq/", timeout=90000)  # 90 secondes de timeout
            
            # Prendre une capture d'écran pour vérifier ce qui est chargé
            await page.screenshot(path=f"{debug_dir}/01_page_loaded.png")
            print(f"Capture d'écran sauvegardée dans {debug_dir}/01_page_loaded.png")
            
            # Attendre que le réseau soit stabilisé
            print("Attente de la stabilisation du réseau...")
            await page.wait_for_load_state("networkidle", timeout=60000)
            print("État réseau stabilisé")
            
            # Prendre une autre capture d'écran
            await page.screenshot(path=f"{debug_dir}/02_network_idle.png") 
            
            print("Vérification de la présence du contenu...")
            # Vérifier si la page contient du contenu
            content_exists = await page.evaluate("""() => {
                return document.body.textContent.includes('FAQ');
            }""")
            
            if not content_exists:
                print("⚠️ Le contenu de la page n'a pas l'air d'être celui attendu")
                # Prendre une capture d'écran
                await page.screenshot(path=f"{debug_dir}/error_no_content.png")
                raise Exception("La page ne contient pas le contenu attendu")
                
            print("Contenu FAQ détecté sur la page")
            
            # Essayons de trouver des titres h3 et h4 peu importe où ils sont
            print("\nRecherche des titres h3 et h4 sur la page...")
            
            # Vérifier la présence des titres h3
            h3_count = await page.evaluate("""() => {
                return document.querySelectorAll('h3').length;
            }""")
            
            print(f"Trouvé {h3_count} titres h3 sur la page")
            
            # Vérifier la présence des titres h4
            h4_count = await page.evaluate("""() => {
                return document.querySelectorAll('h4.title').length;
            }""")
            
            print(f"Trouvé {h4_count} questions h4.title sur la page")
            
            if h3_count == 0 or h4_count == 0:
                print("⚠️ Pas assez de titres h3 ou h4 trouvés")
                await page.screenshot(path=f"{debug_dir}/error_no_titles.png")
                raise Exception("Impossible de trouver suffisamment de titres h3 ou h4")
            
            # Auto-scroll pour s'assurer que tout le contenu est chargé
            print("\nAuto-scroll de la page pour charger tout le contenu...")
            await page.evaluate("""async () => {
                await new Promise((resolve) => {
                    let totalHeight = 0;
                    const distance = 100;
                    const timer = setInterval(() => {
                        const scrollHeight = document.body.scrollHeight;
                        window.scrollBy(0, distance);
                        totalHeight += distance;
                        
                        if (totalHeight >= scrollHeight) {
                            clearInterval(timer);
                            resolve();
                        }
                    }, 50);
                });
            }""")
            print("Auto-scroll terminé")
            
            # Prendre une capture d'écran après le scroll
            await page.screenshot(path=f"{debug_dir}/03_after_scroll.png")
            
            # Extraire les titres des sections (h3) et les questions avec leurs réponses
            print("\nExtraction des titres de section et questions...")
            
            faq_data = await page.evaluate("""() => {
                // Fonction pour nettoyer le texte
                const cleanText = (text) => {
                    if (!text) return '';
                    return text.replace(/\\s+/g, ' ').trim();
                };
                
                // Obtenir tous les titres h3
                const h3Elements = Array.from(document.querySelectorAll('h3'));
                
                // Résultat final
                const result = [];
                
                // Fonction pour trouver la réponse d'une question
                const findAnswerForQuestion = (questionEl) => {
                    let answerEl = null;
                    let current = questionEl.nextElementSibling;
                    
                    // Chercher un div.desc après la question
                    while (current && !answerEl) {
                        if (current.classList.contains('desc')) {
                            answerEl = current;
                            break;
                        }
                        current = current.nextElementSibling;
                    }
                    
                    if (answerEl) {
                        let answerText = '';
                        
                        // Extraire le texte de tous les paragraphes
                        const paragraphs = answerEl.querySelectorAll('p');
                        if (paragraphs.length > 0) {
                            // Joindre le texte de tous les paragraphes
                            answerText = Array.from(paragraphs)
                                .map(p => cleanText(p.textContent))
                                .join(' ');
                        } else {
                            // Si pas de paragraphes, prendre tout le texte
                            answerText = cleanText(answerEl.textContent);
                        }
                        
                        return answerText;
                    }
                    
                    return null;
                };
                
                // Pour chaque titre h3, trouver les questions associées
                h3Elements.forEach(h3El => {
                    const sectionTitle = cleanText(h3El.textContent);
                    
                    // Vérifier si ce titre contient des questions
                    const parent = h3El.parentElement;
                    if (parent) {
                        const h4Questions = parent.querySelectorAll('h4.title');
                        
                        // Pour chaque question h4
                        Array.from(h4Questions).forEach(h4El => {
                            const questionText = cleanText(h4El.textContent);
                            const answerText = findAnswerForQuestion(h4El);
                            
                            if (questionText && answerText) {
                                result.push({
                                    section: sectionTitle,
                                    question: questionText,
                                    answer: answerText
                                });
                            }
                        });
                    }
                });
                
                // Si peu de résultats, essayer une méthode alternative
                if (result.length < 20) {
                    // Récupérer toutes les questions h4.title
                    const allQuestions = document.querySelectorAll('h4.title');
                    
                    Array.from(allQuestions).forEach(h4El => {
                        const questionText = cleanText(h4El.textContent);
                        const answerText = findAnswerForQuestion(h4El);
                        
                        // Tenter de trouver le h3 parent
                        let sectionTitle = "Général";
                        let parent = h4El.parentElement;
                        
                        // Remonter pour trouver un h3
                        while (parent) {
                            const h3 = parent.querySelector('h3');
                            if (h3) {
                                sectionTitle = cleanText(h3.textContent);
                                break;
                            }
                            parent = parent.parentElement;
                            if (!parent) break;
                        }
                        
                        if (questionText && answerText) {
                            // Vérifier si cette question existe déjà
                            const exists = result.some(item => 
                                item.question === questionText && 
                                item.answer === answerText
                            );
                            
                            if (!exists) {
                                result.push({
                                    section: sectionTitle,
                                    question: questionText,
                                    answer: answerText
                                });
                            }
                        }
                    });
                }
                
                return result;
            }""")
            
            print(f"Extraction terminée. Récupéré {len(faq_data)} questions et réponses.")
            
            # Traiter les données et les convertir au format final
            for item in faq_data:
                section_title = item.get('section', 'Général')
                question_text = item.get('question', '')
                answer_text = item.get('answer', '')
                
                # Déterminer la catégorie
                category = determine_category(section_title)
                
                # Ajouter à notre liste finale au format faq.csv
                if question_text and answer_text:
                    faq_item = {
                        "Catégorie": category,
                        "Titre": section_title,
                        "Question": question_text,
                        "Réponse": answer_text
                    }
                    all_faq_data.append(faq_item)
                    
                    # Trouver la section correspondante ou la créer
                    section_found = False
                    for section in sections_data:
                        if section['title'] == section_title:
                            section_found = True
                            question_item = {
                                "question": question_text,
                                "answer": answer_text
                            }
                            section["questions"].append(question_item)
                            break
                    
                    if not section_found:
                        section_id = len(sections_data) + 1
                        sections_data.append({
                            "id": section_id,
                            "title": section_title,
                            "questions": [
                                {
                                    "question": question_text,
                                    "answer": answer_text
                                }
                            ]
                        })
            
            print(f"\nTraitement terminé. {len(all_faq_data)} questions extraites au total.")
            
        except Exception as e:
            print(f"Erreur lors du scraping: {str(e)}")
            # Capturer une capture d'écran en cas d'erreur
            await page.screenshot(path=f"{debug_dir}/error_screenshot.png")
            print(f"Capture d'écran enregistrée dans {debug_dir}/error_screenshot.png")
        finally:
            await browser.close()
    
    if all_faq_data:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Enregistrer en format CSV exactement comme faq.csv (avec point-virgule comme séparateur)
        csv_filename = f"faq_{timestamp}.csv"
        df = pd.DataFrame(all_faq_data)
        df.to_csv(csv_filename, index=False, encoding='utf-8', sep=';')
        print(f"\nFichier CSV au format faq.csv enregistré dans {csv_filename}")
        
        # Enregistrer en JSON pour référence
        json_filename = f"faq_{timestamp}.json"
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(all_faq_data, f, ensure_ascii=False, indent=4)
        print(f"Données JSON enregistrées dans {json_filename}")
        
        # Enregistrer également la structure hiérarchique complète
        sections_filename = f"faq_sections_{timestamp}.json"
        with open(sections_filename, 'w', encoding='utf-8') as f:
            json.dump(sections_data, f, ensure_ascii=False, indent=4)
        print(f"Structure des sections enregistrée dans {sections_filename}")
        
        return all_faq_data
    else:
        return None

def determine_category(section_title):
    """
    Détermine la catégorie en fonction du titre de section
    en se basant sur le format de faq.csv
    """
    # Mapping des mots-clés dans les titres de section vers les catégories de faq.csv
    # Ce mapping est simplifié et devra être ajusté en fonction des résultats
    section_lower = section_title.lower()
    
    # Catégories principales dans faq.csv
    if "formation post-bac" in section_lower:
        return "learn - formation post-bac"
    elif "formation" in section_lower and "métier" in section_lower:
        return "learn- formations métiers diplômantes"
    elif "financement" in section_lower:
        return "learn- formations métiers diplômantes"  # Sous-catégorie Coûts et financements
    elif "recrutement" in section_lower or "sélection" in section_lower:
        return "learn- formations métiers diplômantes"  # Sous-catégorie Processus de recrutement
    elif "secteur" in section_lower and "solidarité" in section_lower:
        return "learn"
    else:
        # Catégorie par défaut
        return "learn"

async def main():
    """Fonction principale d'exécution"""
    await scrape_bioforce_faq_precise()

if __name__ == "__main__":
    asyncio.run(main())