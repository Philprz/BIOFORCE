"""
Script pour tester l'extraction d'un PDF spécifique
"""
import asyncio
import json
import os
import sys
from datetime import datetime

from extractors.pdf_extractor import extract_pdf_content
from utils.classifier import classify_content
from utils.content_tracker import ContentTracker
from utils.language_detector import detect_language
from config import DATA_DIR, CURRENT_DATE

async def test_pdf_extraction(pdf_url, save_to_db=True):
    """
    Teste l'extraction d'un PDF spécifique
    
    Args:
        pdf_url: URL du PDF à tester
        save_to_db: Si True, sauvegarde le contenu dans le tracker
    """
    print(f"Extraction du PDF: {pdf_url}")
    
    try:
        # Extraire le contenu du PDF
        pdf_data = await extract_pdf_content(pdf_url)
        
        if not pdf_data:
            print("Échec de l'extraction du PDF")
            return None
        
        # Détecter la langue
        language = detect_language(pdf_data.get('content', ''))
        
        # Classifier le contenu
        category = classify_content(pdf_url, pdf_data.get('title', ''), pdf_data.get('content', ''))
        
        # Structurer les données
        data = {
            'source_url': pdf_url,
            'title': pdf_data.get('title', ''),
            'content': pdf_data.get('content', ''),
            'metadata': pdf_data.get('metadata', {}),
            'type': 'pdf',
            'language': language,
            'category': category,
            'date_extraction': CURRENT_DATE
        }
        
        print(f"PDF extrait avec succès: {data['title']}")
        print(f"Langue détectée: {language}")
        print(f"Catégorie: {category}")
        print(f"Longueur du contenu: {len(data['content'])} caractères")
        
        # Afficher un extrait du contenu
        content_preview = data['content'][:500] + "..." if len(data['content']) > 500 else data['content']
        print("\nAperçu du contenu:")
        print(content_preview)
        
        # Métadonnées
        print("\nMétadonnées:")
        for key, value in data['metadata'].items():
            print(f"  {key}: {value}")
        
        # Sauvegarde dans le fichier JSON
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(DATA_DIR, f"pdf_test_{timestamp}.json")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"\nDonnées sauvegardées dans: {output_file}")
        
        # Sauvegarde dans la base de données de suivi
        if save_to_db:
            tracker = ContentTracker()
            status, is_changed, previous = tracker.check_content_status(pdf_url, data)
            tracker.update_content_record(pdf_url, data, status)
            
            print(f"\nStatut du contenu: {status}")
            if status == 'updated' and previous:
                print(f"Version précédente: {previous.get('version', 0)}")
        
        return data
        
    except Exception as e:
        print(f"Erreur lors de l'extraction du PDF: {str(e)}")
        return None

async def main():
    """Fonction principale"""
    # Vérifier les arguments
    if len(sys.argv) > 1:
        pdf_url = sys.argv[1]
    else:
        # URL par défaut ou demander à l'utilisateur
        pdf_url = input("Entrez l'URL du PDF à extraire (ou appuyez sur Entrée pour utiliser l'exemple): ")
        if not pdf_url:
            pdf_url = "https://www.bioforce.org/wp-content/uploads/2020/06/2025_Bioforce_LogisticienAH.pdf"
    
    print(f"Test d'extraction du PDF: {pdf_url}")
    await test_pdf_extraction(pdf_url)

if __name__ == "__main__":
    asyncio.run(main())
