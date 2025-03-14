import pandas as pd
import json
from datetime import datetime

def convert_csv_to_json(csv_file, encoding='utf-8', sep=';'):
    """
    Convertit un fichier CSV en JSON
    
    Args:
        csv_file (str): Chemin vers le fichier CSV à convertir
        encoding (str): Encodage du fichier CSV
        sep (str): Séparateur utilisé dans le fichier CSV
        
    Returns:
        str: Chemin vers le fichier JSON créé
    """
    print(f"Conversion de {csv_file} en JSON...")
    
    # Lire le fichier CSV
    try:
        df = pd.read_csv(csv_file, encoding=encoding, sep=sep)
        print(f"Fichier CSV lu avec succès. {len(df)} entrées trouvées.")
    except Exception as e:
        print(f"Erreur lors de la lecture du fichier CSV: {str(e)}")
        return None
    
    # Convertir le DataFrame en liste de dictionnaires
    data = df.to_dict(orient='records')
    print("Conversion en dictionnaires terminée.")
    
    # Générer le nom du fichier de sortie
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = csv_file.replace('.csv', f'_{timestamp}.json')
    
    # Écrire les données au format JSON
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Conversion terminée. Fichier JSON créé: {output_file}")
        return output_file
    except Exception as e:
        print(f"Erreur lors de l'écriture du fichier JSON: {str(e)}")
        return None

if __name__ == "__main__":
    # Convertir Faq.csv en JSON
    convert_csv_to_json("Faq.csv")
