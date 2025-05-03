import pdfkit

import os
print("🔍 Dossier courant :", os.getcwd())

# Chemin vers wkhtmltopdf.exe (à adapter si différent)
WKHTMLTOPDF_PATH = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
pdfkit_config = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)
html_files = [os.path.join(os.path.dirname(__file__), f"Page{i}.html") for i in range(1, 11)]

# Fichier de sortie
output_pdf = "presentation.pdf"

# Conversion en un seul PDF
try:
    pdfkit.from_file(html_files, output_pdf, configuration=pdfkit_config)
    print(f"✅ PDF généré avec succès : {output_pdf}")
except Exception as e:
    print(f"❌ Erreur : {e}")
