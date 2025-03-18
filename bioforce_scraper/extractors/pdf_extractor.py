"""
Module pour l'extraction de contenu à partir des fichiers PDF
"""
import io
import logging
import os
import re
import tempfile
from typing import Dict, Any, Optional

import aiohttp
import pytesseract
from PIL import Image
from pdfminer.high_level import extract_text
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser
from PyPDF2 import PdfReader

# Import absolus pour éviter les problèmes lorsque le module est importé depuis l'API
import sys
import pathlib
# Ajouter le répertoire parent au path pour pouvoir importer les modules
sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))

from bioforce_scraper.config import LOG_FILE, PDF_DIR, PDF_MAX_SIZE
from bioforce_scraper.utils.logger import setup_logger

logger = setup_logger(__name__, LOG_FILE)

async def extract_pdf_content(url: str) -> Dict[str, Any]:
    """
    Télécharge et extrait le contenu d'un fichier PDF
    
    Args:
        url: L'URL du fichier PDF
        
    Returns:
        Un dictionnaire contenant le contenu extrait
    """
    try:
        # Déterminer le nom de fichier à partir de l'URL
        filename = url.split('/')[-1]
        local_path = os.path.join(PDF_DIR, filename)
        
        # Télécharger le fichier PDF
        pdf_data = await download_pdf(url)
        if not pdf_data:
            logger.warning(f"Impossible de télécharger le PDF: {url}")
            return None
        
        # Sauvegarder une copie locale
        with open(local_path, 'wb') as f:
            f.write(pdf_data)
        
        # Extraire le texte du PDF avec PyPDF2
        text_pypdf = extract_text_pypdf(pdf_data)
        
        # Si PyPDF2 échoue, essayer avec pdfminer
        if not text_pypdf or len(text_pypdf.strip()) < 100:
            logger.info(f"PyPDF2 n'a pas extrait suffisamment de texte, essai avec pdfminer pour {url}")
            text_pdfminer = extract_text_pdfminer(local_path)
            
            # Si pdfminer échoue aussi, essayer l'OCR si applicable
            if not text_pdfminer or len(text_pdfminer.strip()) < 100:
                logger.info(f"Pdfminer n'a pas extrait suffisamment de texte, essai OCR pour {url}")
                text_ocr = extract_text_ocr(local_path)
                if text_ocr:
                    main_text = text_ocr
                else:
                    main_text = text_pdfminer or text_pypdf or ""
            else:
                main_text = text_pdfminer
        else:
            main_text = text_pypdf
        
        # Extraire les métadonnées
        metadata = extract_pdf_metadata(pdf_data)
        
        # Déterminer le titre
        title = get_pdf_title(url, metadata)
        
        # Nettoyer le texte
        clean_text = clean_pdf_text(main_text)
        
        return {
            'title': title,
            'content': clean_text,
            'metadata': metadata,
            'local_path': local_path
        }
    
    except Exception as e:
        logger.error(f"Erreur lors de l'extraction du PDF {url}: {str(e)}")
        return None

async def download_pdf(url: str) -> Optional[bytes]:
    """Télécharge un fichier PDF à partir d'une URL"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    logger.warning(f"Erreur HTTP {response.status} pour {url}")
                    return None
                
                # Vérifier la taille
                content_length = response.headers.get('Content-Length')
                if content_length and int(content_length) > PDF_MAX_SIZE:
                    logger.warning(f"PDF trop volumineux ({content_length} bytes): {url}")
                    return None
                
                # Vérifier le type de contenu
                content_type = response.headers.get('Content-Type', '')
                if 'application/pdf' not in content_type and '.pdf' not in url.lower():
                    logger.warning(f"Le contenu n'est pas un PDF: {content_type}, URL: {url}")
                    return None
                
                return await response.read()
    
    except Exception as e:
        logger.error(f"Erreur lors du téléchargement du PDF {url}: {str(e)}")
        return None

def extract_text_pypdf(pdf_data: bytes) -> str:
    """Extrait le texte d'un PDF en utilisant PyPDF2"""
    try:
        with io.BytesIO(pdf_data) as pdf_file:
            pdf_reader = PdfReader(pdf_file)
            text_parts = []
            
            for page in pdf_reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            
            return "\n\n".join(text_parts)
    
    except Exception as e:
        logger.error(f"Erreur lors de l'extraction du texte avec PyPDF2: {str(e)}")
        return ""

def extract_text_pdfminer(pdf_path: str) -> str:
    """Extrait le texte d'un PDF en utilisant pdfminer.six"""
    try:
        return extract_text(pdf_path)
    
    except Exception as e:
        logger.error(f"Erreur lors de l'extraction du texte avec pdfminer: {str(e)}")
        return ""

def extract_text_ocr(pdf_path: str) -> str:
    """
    Extrait le texte d'un PDF en utilisant OCR (pytesseract)
    Note: Cela nécessite que Tesseract OCR soit installé sur le système
    """
    try:
        # Convertir les 5 premières pages du PDF en images pour l'OCR
        import fitz  # PyMuPDF
        
        doc = fitz.open(pdf_path)
        text_parts = []
        
        # Limiter à 5 pages pour éviter des temps d'exécution trop longs
        max_pages = min(5, len(doc))
        
        for page_num in range(max_pages):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                pix.save(tmp.name)
                tmp_path = tmp.name
            
            # Exécuter OCR sur l'image
            try:
                image = Image.open(tmp_path)
                text = pytesseract.image_to_string(image, lang='fra+eng')
                if text.strip():
                    text_parts.append(text)
                image.close()
            finally:
                # Nettoyer
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
        
        return "\n\n".join(text_parts)
    
    except Exception as e:
        logger.error(f"Erreur lors de l'extraction OCR du PDF: {str(e)}")
        return ""

def extract_pdf_metadata(pdf_data: bytes) -> Dict[str, Any]:
    """Extrait les métadonnées d'un PDF"""
    metadata = {}
    
    try:
        with io.BytesIO(pdf_data) as pdf_file:
            # Extraction avec PyPDF2
            pdf_reader = PdfReader(pdf_file)
            if pdf_reader.metadata:
                metadata.update({
                    'title': pdf_reader.metadata.get('/Title', ''),
                    'author': pdf_reader.metadata.get('/Author', ''),
                    'subject': pdf_reader.metadata.get('/Subject', ''),
                    'creator': pdf_reader.metadata.get('/Creator', ''),
                    'producer': pdf_reader.metadata.get('/Producer', ''),
                    'creation_date': pdf_reader.metadata.get('/CreationDate', ''),
                    'modification_date': pdf_reader.metadata.get('/ModDate', '')
                })
            
            # Ajouter le nombre de pages
            metadata['page_count'] = len(pdf_reader.pages)
            
        # Extraction supplémentaire avec pdfminer
        with io.BytesIO(pdf_data) as pdf_file:
            parser = PDFParser(pdf_file)
            doc = PDFDocument(parser)
            if 'Info' in doc.info:
                for key, value in doc.info[0].items():
                    if isinstance(value, bytes):
                        try:
                            value = value.decode('utf-8', errors='ignore')
                        except:
                            value = str(value)
                    metadata[key] = value
    
    except Exception as e:
        logger.error(f"Erreur lors de l'extraction des métadonnées PDF: {str(e)}")
    
    return metadata

def get_pdf_title(url: str, metadata: Dict[str, Any]) -> str:
    """Détermine le titre du PDF"""
    # Essayer d'obtenir le titre à partir des métadonnées
    title = metadata.get('title', '')
    
    # Si pas de titre dans les métadonnées, utiliser le nom du fichier
    if not title:
        title = url.split('/')[-1].replace('.pdf', '').replace('_', ' ').replace('-', ' ').title()
    
    return title

def clean_pdf_text(text: str) -> str:
    """
    Nettoie le texte extrait d'un PDF
    
    Args:
        text: Le texte à nettoyer
        
    Returns:
        Le texte nettoyé
    """
    if not text:
        return ""
        
    # Supprimer les espaces multiples
    text = re.sub(r'\s+', ' ', text)
    
    # Supprimer les caractères de contrôle
    text = re.sub(r'[\x00-\x1F\x7F]', '', text)
    
    # Supprimer les lignes vides
    text = re.sub(r'\n\s*\n', '\n', text)
    
    return text.strip()

async def extract_text_from_pdf(url: str) -> Dict[str, Any]:
    """
    Alias pour extract_pdf_content pour assurer la compatibilité avec les imports existants
    
    Args:
        url: L'URL du fichier PDF
        
    Returns:
        Un dictionnaire contenant le contenu et les métadonnées extraits
    """
    return await extract_pdf_content(url)
