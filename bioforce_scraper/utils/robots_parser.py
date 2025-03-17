"""
Module pour l'analyse des fichiers robots.txt
"""
import logging
import urllib.parse
from typing import List, Dict, Set, Optional

import aiohttp

from bioforce_scraper.config import LOG_FILE, USER_AGENT
from bioforce_scraper.utils.logger import setup_logger

logger = setup_logger(__name__, LOG_FILE)

class RobotsParser:
    """
    Parser pour les fichiers robots.txt
    """
    def __init__(self, base_url: str):
        """
        Initialise le parser robots.txt
        
        Args:
            base_url: URL de base du site
        """
        self.base_url = base_url
        self.robots_url = urllib.parse.urljoin(base_url, '/robots.txt')
        self.disallowed: Set[str] = set()
        self.allow_all = True
    
    async def load(self) -> bool:
        """
        Charge et parse le fichier robots.txt
        
        Returns:
            True si le chargement a réussi, False sinon
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.robots_url) as response:
                    if response.status != 200:
                        logger.warning(f"Impossible de récupérer robots.txt: {response.status}")
                        return False
                    
                    content = await response.text()
                    return self._parse_robots_txt(content)
        
        except Exception as e:
            logger.error(f"Erreur lors du chargement de robots.txt: {str(e)}")
            return False
    
    def _parse_robots_txt(self, content: str) -> bool:
        """
        Parse le contenu du fichier robots.txt
        
        Args:
            content: Contenu du fichier robots.txt
            
        Returns:
            True si le parsing a réussi, False sinon
        """
        try:
            lines = content.strip().split('\n')
            current_agent = None
            relevant_section = False
            
            for line in lines:
                line = line.strip()
                
                # Ignorer les commentaires et les lignes vides
                if not line or line.startswith('#'):
                    continue
                
                # Découper la ligne en parties
                parts = line.split(':', 1)
                if len(parts) != 2:
                    continue
                
                directive, value = parts[0].strip().lower(), parts[1].strip()
                
                # Traiter les directives
                if directive == 'user-agent':
                    current_agent = value
                    # Vérifier si cette section s'applique à notre agent
                    relevant_section = value == '*' or USER_AGENT.lower().startswith(value.lower())
                
                elif directive == 'disallow' and relevant_section and value:
                    self.disallowed.add(value)
                
                elif directive == 'allow' and relevant_section and value:
                    # Les règles Allow annulent les règles Disallow spécifiques
                    if value in self.disallowed:
                        self.disallowed.remove(value)
            
            self.allow_all = len(self.disallowed) == 0
            logger.info(f"robots.txt parsé: {len(self.disallowed)} règles d'exclusion")
            return True
        
        except Exception as e:
            logger.error(f"Erreur lors du parsing de robots.txt: {str(e)}")
            return False
    
    def can_fetch(self, url: str) -> bool:
        """
        Vérifie si une URL peut être scrapée selon robots.txt
        
        Args:
            url: URL à vérifier
            
        Returns:
            True si l'URL peut être scrapée, False sinon
        """
        if self.allow_all:
            return True
        
        # Extraire le chemin relatif de l'URL
        parsed_url = urllib.parse.urlparse(url)
        path = parsed_url.path
        
        # Vérifier chaque règle Disallow
        for disallowed_path in self.disallowed:
            if path.startswith(disallowed_path):
                logger.debug(f"URL non autorisée par robots.txt: {url}")
                return False
        
        return True
