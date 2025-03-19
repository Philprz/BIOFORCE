"""
Module pour le filtrage intelligent du contenu par GPT avant indexation
"""
from typing import Dict, Any, List, Tuple

from openai import AsyncOpenAI

from bioforce_scraper.config import OPENAI_API_KEY, COMPLETION_MODEL, LOG_FILE
from bioforce_scraper.utils.logger import setup_logger
from bioforce_scraper.utils.language_detector import detect_language

# Configuration du logger
logger = setup_logger(__name__, LOG_FILE)

class ContentFilterGPT:
    """
    Classe pour filtrer et améliorer le contenu avec GPT avant indexation
    """
    
    def __init__(self):
        """
        Initialise le filtre de contenu GPT
        """
        self.openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    
    async def filter_faq_content(self, faq_items: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Filtre les éléments FAQ avec GPT pour ne garder que les informations utiles
        
        Args:
            faq_items: Liste des éléments FAQ à filtrer
            
        Returns:
            Tuple contenant (éléments conservés, éléments filtrés)
        """
        logger.info(f"Filtrage intelligent de {len(faq_items)} éléments FAQ avec {COMPLETION_MODEL}")
        
        kept_items = []
        filtered_items = []
        
        for item in faq_items:
            try:
                # Déterminer la langue si ce n'est pas déjà fait
                if "language" not in item:
                    item["language"] = detect_language(item.get("answer", ""))
                
                is_french = item["language"] == "fr"
                
                # Construire le prompt en fonction de la langue
                system_prompt = """
                Tu es un assistant spécialisé dans le filtrage de contenu pour un chatbot de l'organisation Bioforce.
                Tu doit évaluer si l'élément de FAQ fourni est utile pour répondre aux questions des candidats 
                concernant les formations, le processus de sélection et les modalités d'inscription.
                
                CRITÈRES DE SÉLECTION:
                1. Pertinence pour les candidats à une formation Bioforce
                2. Actualité et précision de l'information
                3. Format adapté aux requêtes d'un chatbot
                
                Ton rôle est d'évaluer l'élément et de le reformuler/améliorer si nécessaire.
                """
                
                if is_french:
                    user_prompt = f"""
                    Voici un élément de FAQ extrait du site Bioforce:
                    
                    Catégorie: {item.get('category', 'Non spécifiée')}
                    Question: {item.get('question', '')}
                    Réponse: {item.get('answer', '')}
                    
                    1. Cet élément est-il utile pour le chatbot? (Réponds par OUI ou NON)
                    2. Si OUI, propose une version améliorée de la réponse qui conserve toutes les informations importantes 
                       mais qui est optimisée pour un chatbot (plus concise, structurée, informative).
                    3. Si NON, explique brièvement pourquoi.
                    
                    Commence ta réponse par "DÉCISION: OUI" ou "DÉCISION: NON".
                    """
                else:
                    user_prompt = f"""
                    Here is a FAQ item extracted from the Bioforce website:
                    
                    Category: {item.get('category', 'Not specified')}
                    Question: {item.get('question', '')}
                    Answer: {item.get('answer', '')}
                    
                    1. Is this item useful for the chatbot? (Answer with YES or NO)
                    2. If YES, provide an improved version of the answer that keeps all important information
                       but is optimized for a chatbot (more concise, structured, informative).
                    3. If NO, briefly explain why.
                    
                    Start your response with "DECISION: YES" or "DECISION: NO".
                    """
                
                response = await self._evaluate_with_gpt(system_prompt, user_prompt)
                
                # Traiter la réponse
                if response.startswith("DÉCISION: OUI") or response.startswith("DECISION: YES"):
                    improved_answer = self._extract_improved_content(response, is_french)
                    improved_item = item.copy()
                    
                    if improved_answer:
                        improved_item["answer"] = improved_answer
                        improved_item["gpt_enhanced"] = True
                    
                    kept_items.append(improved_item)
                    logger.info(f"Élément FAQ conservé et amélioré: {item.get('question', '')[:50]}...")
                else:
                    filtered_items.append(item)
                    logger.info(f"Élément FAQ filtré: {item.get('question', '')[:50]}...")
                
            except Exception as e:
                logger.error(f"Erreur lors du filtrage par GPT: {e}")
                # En cas d'erreur, conserver l'élément original par précaution
                kept_items.append(item)
        
        return kept_items, filtered_items
    
    async def filter_page_content(self, page_content: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
        """
        Filtre et améliore le contenu d'une page HTML avec GPT
        
        Args:
            page_content: Dictionnaire contenant le contenu de la page
            
        Returns:
            Tuple contenant (contenu amélioré, booléen indiquant si le contenu est utile)
        """
        if not page_content.get("content"):
            return page_content, False
            
        try:
            # Déterminer la langue
            content_text = page_content.get("content", "")
            language = detect_language(content_text)
            is_french = language == "fr"
            
            # Limiter la taille du contenu pour le prompt
            max_content_length = 5000
            if len(content_text) > max_content_length:
                truncated_content = content_text[:max_content_length] + "... (contenu tronqué)"
            else:
                truncated_content = content_text
            
            # Construire le prompt
            system_prompt = """
            Tu es un assistant spécialisé dans le filtrage et l'amélioration de contenu pour un chatbot de l'organisation Bioforce.
            Tu doit évaluer si le contenu de la page est utile pour répondre aux questions des candidats concernant les formations, 
            le processus de sélection et les modalités d'inscription.
            
            CRITÈRES DE SÉLECTION:
            1. Pertinence pour les candidats à une formation Bioforce
            2. Actualité et précision de l'information
            3. Format adapté aux requêtes d'un chatbot
            
            Ton rôle est de:
            1. Évaluer si le contenu est utile pour le chatbot
            2. Si oui, extraire et structurer les informations clés
            3. Éliminer les sections promotionnelles, techniques ou sans valeur informative
            """
            
            if is_french:
                user_prompt = f"""
                Voici le contenu d'une page du site Bioforce:
                
                Titre: {page_content.get('title', 'Sans titre')}
                URL: {page_content.get('url', '')}
                
                CONTENU:
                {truncated_content}
                
                1. Ce contenu est-il utile pour le chatbot? (Réponds par OUI ou NON)
                2. Si OUI:
                   a) Extrais uniquement les informations pertinentes pour les candidats
                   b) Structure le contenu de façon claire, concise et informative
                   c) Élimine tout texte promotionnel, technique ou sans valeur informative
                3. Si NON, explique brièvement pourquoi.
                
                Commence ta réponse par "DÉCISION: OUI" ou "DÉCISION: NON".
                """
            else:
                user_prompt = f"""
                Here is the content of a page from the Bioforce website:
                
                Title: {page_content.get('title', 'No title')}
                URL: {page_content.get('url', '')}
                
                CONTENT:
                {truncated_content}
                
                1. Is this content useful for the chatbot? (Answer with YES or NO)
                2. If YES:
                   a) Extract only the information relevant to candidates
                   b) Structure the content in a clear, concise, and informative way
                   c) Remove any promotional, technical, or non-informative text
                3. If NO, briefly explain why.
                
                Start your response with "DECISION: YES" or "DECISION: NO".
                """
            
            response = await self._evaluate_with_gpt(system_prompt, user_prompt)
            
            # Traiter la réponse
            if response.startswith("DÉCISION: OUI") or response.startswith("DECISION: YES"):
                improved_content = self._extract_improved_content(response, is_french)
                
                if improved_content:
                    enhanced_page = page_content.copy()
                    enhanced_page["content"] = improved_content
                    enhanced_page["gpt_enhanced"] = True
                    return enhanced_page, True
                else:
                    return page_content, True
            else:
                return page_content, False
                
        except Exception as e:
            logger.error(f"Erreur lors du filtrage du contenu de page par GPT: {e}")
            return page_content, True  # En cas d'erreur, considérer le contenu comme utile par prudence
    
    async def filter_pdf_content(self, pdf_content: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
        """
        Filtre et améliore le contenu d'un PDF avec GPT
        
        Args:
            pdf_content: Dictionnaire contenant le contenu du PDF
            
        Returns:
            Tuple contenant (contenu amélioré, booléen indiquant si le contenu est utile)
        """
        if not pdf_content.get("content"):
            return pdf_content, False
            
        try:
            # Déterminer la langue
            content_text = pdf_content.get("content", "")
            language = detect_language(content_text)
            is_french = language == "fr"
            
            # Limiter la taille du contenu pour le prompt
            max_content_length = 5000
            if len(content_text) > max_content_length:
                truncated_content = content_text[:max_content_length] + "... (contenu tronqué)"
            else:
                truncated_content = content_text
            
            # Construire le prompt
            system_prompt = """
            Tu es un assistant spécialisé dans le filtrage et l'amélioration de contenu pour un chatbot de l'organisation Bioforce.
            Tu doit évaluer si le contenu du PDF est utile pour répondre aux questions des candidats concernant les formations, 
            le processus de sélection et les modalités d'inscription.
            
            CRITÈRES DE SÉLECTION:
            1. Pertinence pour les candidats à une formation Bioforce
            2. Actualité et précision de l'information
            3. Format adapté aux requêtes d'un chatbot
            
            Ton rôle est de:
            1. Évaluer si le contenu est utile pour le chatbot
            2. Si oui, extraire et structurer les informations clés
            3. Éliminer les sections promotionnelles, techniques ou sans valeur informative
            """
            
            if is_french:
                user_prompt = f"""
                Voici le contenu d'un PDF du site Bioforce:
                
                Titre: {pdf_content.get('title', 'Sans titre')}
                URL: {pdf_content.get('url', '')}
                
                CONTENU:
                {truncated_content}
                
                1. Ce contenu est-il utile pour le chatbot? (Réponds par OUI ou NON)
                2. Si OUI:
                   a) Extrais uniquement les informations pertinentes pour les candidats
                   b) Structure le contenu de façon claire, concise et informative
                   c) Élimine tout texte promotionnel, technique ou sans valeur informative
                3. Si NON, explique brièvement pourquoi.
                
                Commence ta réponse par "DÉCISION: OUI" ou "DÉCISION: NON".
                """
            else:
                user_prompt = f"""
                Here is the content of a PDF from the Bioforce website:
                
                Title: {pdf_content.get('title', 'No title')}
                URL: {pdf_content.get('url', '')}
                
                CONTENT:
                {truncated_content}
                
                1. Is this content useful for the chatbot? (Answer with YES or NO)
                2. If YES:
                   a) Extract only the information relevant to candidates
                   b) Structure the content in a clear, concise, and informative way
                   c) Remove any promotional, technical, or non-informative text
                3. If NO, briefly explain why.
                
                Start your response with "DECISION: YES" or "DECISION: NO".
                """
            
            response = await self._evaluate_with_gpt(system_prompt, user_prompt)
            
            # Traiter la réponse
            if response.startswith("DÉCISION: OUI") or response.startswith("DECISION: YES"):
                improved_content = self._extract_improved_content(response, is_french)
                
                if improved_content:
                    enhanced_pdf = pdf_content.copy()
                    enhanced_pdf["content"] = improved_content
                    enhanced_pdf["gpt_enhanced"] = True
                    return enhanced_pdf, True
                else:
                    return pdf_content, True
            else:
                return pdf_content, False
                
        except Exception as e:
            logger.error(f"Erreur lors du filtrage du contenu PDF par GPT: {e}")
            return pdf_content, True  # En cas d'erreur, considérer le contenu comme utile par prudence
    
    async def _evaluate_with_gpt(self, system_prompt: str, user_prompt: str) -> str:
        """
        Évalue le contenu avec GPT
        
        Args:
            system_prompt: Prompt système
            user_prompt: Prompt utilisateur
            
        Returns:
            Réponse de GPT
        """
        try:
            response = await self.openai_client.chat.completions.create(
                model=COMPLETION_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=800
            )
            
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Erreur lors de l'appel à GPT: {e}")
            raise
    
    def _extract_improved_content(self, gpt_response: str, is_french: bool) -> str:
        """
        Extrait le contenu amélioré de la réponse GPT
        
        Args:
            gpt_response: Réponse de GPT
            is_french: Indique si le contenu est en français
            
        Returns:
            Contenu amélioré
        """
        decision_text = "DÉCISION: OUI" if is_french else "DECISION: YES"
        
        if decision_text in gpt_response:
            # Tenter d'extraire le contenu amélioré
            improved_parts = gpt_response.split(decision_text)
            if len(improved_parts) > 1:
                improved_content = improved_parts[1].strip()
                
                # Chercher des sections spécifiques si existantes
                for marker in ["version améliorée", "contenu amélioré", "improved version", "improved content", 
                               "structured content", "contenu structuré", "information pertinente", "relevant information"]:
                    if marker.lower() in improved_content.lower():
                        parts = improved_content.lower().split(marker.lower(), 1)
                        if len(parts) > 1:
                            return parts[1].strip()
                
                return improved_content
        return ""
