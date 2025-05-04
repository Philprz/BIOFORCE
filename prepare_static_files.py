import re
import shutil
from pathlib import Path

def replace_color_in_file(file_path, old_colors, new_color):
    """Remplace toutes les occurrences des couleurs spécifiées dans un fichier"""
    if not file_path.exists():
        print(f"Fichier introuvable: {file_path}")
        return False
    
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # Créer un pattern regex qui correspond à toutes les anciennes couleurs
        pattern = '|'.join(map(re.escape, old_colors))
        
        # Remplacer toutes les occurrences
        modified_content = re.sub(pattern, new_color, content, flags=re.IGNORECASE)
        
        # Si des modifications ont été apportées
        if modified_content != content:
            with open(file_path, 'w', encoding='utf-8') as file:
                file.write(modified_content)
            return True
        
        return False
    except Exception as e:
        print(f"Erreur lors du traitement du fichier {file_path}: {e}")
        return False

def main():
    # Définir les chemins
    base_dir = Path.cwd()  # Dossier actuel (où le script est exécuté)
    demo_dir = base_dir / "demo_interface"
    static_dir = base_dir / "static"
    
    # Définir les couleurs à remplacer
    old_colors = ['#FF6C42', '#ff8113', '#e74324', '#FF5733', '#FF6C42']
    new_color = '#E84424'
    
    # Créer le dossier static s'il n'existe pas
    static_dir.mkdir(exist_ok=True)
    
    print("=== MISE À JOUR DES FICHIERS BIOFORCE ===")
    print(f"Dossier de base: {base_dir}")
    print(f"Dossier démo: {demo_dir}")
    print(f"Dossier static: {static_dir}")
    print(f"Remplacement des couleurs: {', '.join(old_colors)} -> {new_color}")
    
    # Copier tous les fichiers du dossier demo_interface vers static
    files_copied = 0
    files_modified = 0
    
    if not demo_dir.exists():
        print(f"ERREUR: Le dossier demo_interface n'existe pas: {demo_dir}")
        return
    
    # Lister les fichiers et dossiers dans demo_dir
    for item in demo_dir.glob('**/*'):
        # Pour les dossiers, créer le même dossier dans static
        if item.is_dir():
            target_dir = static_dir / item.relative_to(demo_dir)
            target_dir.mkdir(exist_ok=True)
            continue
        
        # Pour les fichiers, les copier vers static
        source_file = item
        target_file = static_dir / item.relative_to(demo_dir)
        
        # Créer les dossiers parents si nécessaires
        target_file.parent.mkdir(exist_ok=True, parents=True)
        
        # Copier le fichier
        shutil.copy2(source_file, target_file)
        files_copied += 1
        print(f"Copié: {target_file.relative_to(static_dir)}")
        
        # Remplacer les couleurs dans les fichiers CSS et HTML
        if target_file.suffix.lower() in ['.css', '.html', '.js']:
            if replace_color_in_file(target_file, old_colors, new_color):
                files_modified += 1
                print(f"  - Couleurs remplacées dans {target_file.relative_to(static_dir)}")
    
    print("\n=== RÉSUMÉ ===")
    print(f"Fichiers copiés: {files_copied}")
    print(f"Fichiers modifiés (couleurs): {files_modified}")
    print("\nModifiez votre fichier bioforce_api_chatbot.py pour ajouter:")
    print("@app.get(\"/\")")
    print("async def root():")
    print("    \"\"\"Redirige vers l'interface utilisateur du chatbot\"\"\"")
    print("    return RedirectResponse(url=\"/static/index.html\")")
    print("\nPour accéder à votre interface, démarrez votre application et naviguez vers http://localhost:8000")

if __name__ == "__main__":
    main()