"""
Module pour le suivi des contenus déjà extraits et la détection des changements
"""
import hashlib
import json
import logging
import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

from bioforce_scraper.config import DATA_DIR, LOG_FILE
from bioforce_scraper.utils.logger import setup_logger

logger = setup_logger(__name__, LOG_FILE)

class ContentTracker:
    """
    Système de suivi des contenus pour détecter les nouveaux contenus 
    et les mises à jour de contenu existant
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialise le tracker de contenu
        
        Args:
            db_path: Chemin vers la base de données SQLite (optionnel)
        """
        if db_path is None:
            db_path = os.path.join(DATA_DIR, 'content_history.db')
            
        self.db_path = db_path
        self._initialize_db()
        
    def _initialize_db(self):
        """Initialise la base de données si elle n'existe pas"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Table pour stocker l'historique des URLs
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS content_history (
                    url TEXT PRIMARY KEY,
                    content_hash TEXT,
                    title TEXT,
                    category TEXT,
                    type TEXT,
                    last_modified TEXT,
                    last_checked TEXT,
                    version INTEGER,
                    metadata TEXT
                )
            ''')
            
            # Table pour stocker les hachages des versions précédentes
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS content_versions (
                    url TEXT,
                    version INTEGER,
                    content_hash TEXT,
                    timestamp TEXT,
                    PRIMARY KEY (url, version),
                    FOREIGN KEY (url) REFERENCES content_history(url) ON DELETE CASCADE
                )
            ''')
            
            # Index pour accélérer les recherches
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_url ON content_history(url)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_category ON content_history(category)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_type ON content_history(type)')
            
            conn.commit()
            logger.info(f"Base de données initialisée: {self.db_path}")
            
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation de la base de données: {str(e)}")
            
        finally:
            if conn:
                conn.close()
    
    def compute_content_hash(self, content: Dict[str, Any]) -> str:
        """
        Calcule un hachage du contenu pour détecter les changements
        
        Args:
            content: Dictionnaire contenant les données extraites
            
        Returns:
            Hachage SHA-256 du contenu
        """
        # Extraire les parties significatives pour le hachage
        hash_content = {
            'title': content.get('title', ''),
            'content': content.get('content', ''),
            'headings': content.get('headings', [])
        }
        
        # Convertir en JSON et calculer le hachage
        content_str = json.dumps(hash_content, sort_keys=True)
        return hashlib.sha256(content_str.encode('utf-8')).hexdigest()
    
    def check_content_status(self, url: str, content: Dict[str, Any]) -> Tuple[str, bool, Optional[Dict]]:
        """
        Vérifie si le contenu est nouveau, modifié ou inchangé
        
        Args:
            url: URL du contenu
            content: Dictionnaire contenant les données extraites
            
        Returns:
            Tuple (status, is_changed, previous_version)
            status: 'new', 'updated', 'unchanged'
            is_changed: True si le contenu a changé, False sinon
            previous_version: Version précédente du contenu si modifié, None sinon
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Calculer le hachage du contenu actuel
            current_hash = self.compute_content_hash(content)
            
            # Vérifier si l'URL existe déjà dans la base
            cursor.execute('SELECT content_hash, title, metadata, version FROM content_history WHERE url = ?', (url,))
            result = cursor.fetchone()
            
            if not result:
                # URL jamais vue auparavant
                logger.info(f"Nouveau contenu détecté: {url}")
                return 'new', True, None
            
            previous_hash, previous_title, previous_metadata, version = result
            previous_metadata = json.loads(previous_metadata) if previous_metadata else {}
            
            if current_hash == previous_hash:
                # Contenu inchangé
                logger.debug(f"Contenu inchangé: {url}")
                return 'unchanged', False, {
                    'title': previous_title,
                    'content_hash': previous_hash,
                    'version': version,
                    'metadata': previous_metadata
                }
            else:
                # Contenu modifié
                logger.info(f"Contenu mis à jour détecté: {url}")
                return 'updated', True, {
                    'title': previous_title,
                    'content_hash': previous_hash,
                    'version': version,
                    'metadata': previous_metadata
                }
        
        except Exception as e:
            logger.error(f"Erreur lors de la vérification du statut du contenu: {str(e)}")
            return 'error', True, None
            
        finally:
            if conn:
                conn.close()
    
    def update_content_record(self, url: str, content: Dict[str, Any], status: str) -> bool:
        """
        Met à jour ou crée un enregistrement de contenu dans la base de données
        
        Args:
            url: URL du contenu
            content: Dictionnaire contenant les données extraites
            status: Statut du contenu ('new', 'updated', 'unchanged')
            
        Returns:
            True si la mise à jour a réussi, False sinon
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            current_time = datetime.now().isoformat()
            content_hash = self.compute_content_hash(content)
            metadata_json = json.dumps(content.get('metadata', {}))
            
            if status == 'new':
                # Insérer un nouvel enregistrement
                cursor.execute('''
                    INSERT INTO content_history 
                    (url, content_hash, title, category, type, last_modified, last_checked, version, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    url, 
                    content_hash, 
                    content.get('title', ''), 
                    content.get('category', 'général'),
                    content.get('type', 'html'),
                    current_time,
                    current_time,
                    1,  # Version initiale
                    metadata_json
                ))
                
                # Insérer également dans la table des versions
                cursor.execute('''
                    INSERT INTO content_versions
                    (url, version, content_hash, timestamp)
                    VALUES (?, ?, ?, ?)
                ''', (url, 1, content_hash, current_time))
                
            elif status == 'updated':
                # Récupérer la version actuelle
                cursor.execute('SELECT version FROM content_history WHERE url = ?', (url,))
                current_version = cursor.fetchone()[0]
                new_version = current_version + 1
                
                # Insérer la nouvelle version dans la table des versions
                cursor.execute('''
                    INSERT INTO content_versions
                    (url, version, content_hash, timestamp)
                    VALUES (?, ?, ?, ?)
                ''', (url, new_version, content_hash, current_time))
                
                # Mettre à jour l'enregistrement principal
                cursor.execute('''
                    UPDATE content_history 
                    SET content_hash = ?, title = ?, category = ?, last_modified = ?, 
                        last_checked = ?, version = ?, metadata = ?
                    WHERE url = ?
                ''', (
                    content_hash,
                    content.get('title', ''),
                    content.get('category', 'général'),
                    current_time,
                    current_time,
                    new_version,
                    metadata_json,
                    url
                ))
                
            else:  # 'unchanged'
                # Mettre à jour uniquement la date de dernière vérification
                cursor.execute('''
                    UPDATE content_history
                    SET last_checked = ?
                    WHERE url = ?
                ''', (current_time, url))
            
            conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du contenu dans la base de données: {str(e)}")
            if conn:
                conn.rollback()
            return False
            
        finally:
            if conn:
                conn.close()
    
    def get_content_stats(self) -> Dict[str, Any]:
        """
        Récupère des statistiques sur les contenus enregistrés
        
        Returns:
            Dictionnaire contenant les statistiques
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            stats = {}
            
            # Nombre total d'URLs
            cursor.execute('SELECT COUNT(*) FROM content_history')
            stats['total_urls'] = cursor.fetchone()[0]
            
            # Répartition par type
            cursor.execute('SELECT type, COUNT(*) FROM content_history GROUP BY type')
            stats['by_type'] = {type_: count for type_, count in cursor.fetchall()}
            
            # Répartition par catégorie
            cursor.execute('SELECT category, COUNT(*) FROM content_history GROUP BY category')
            stats['by_category'] = {category: count for category, count in cursor.fetchall()}
            
            # URLs les plus récemment modifiées
            cursor.execute('''
                SELECT url, title, last_modified, version 
                FROM content_history 
                ORDER BY last_modified DESC 
                LIMIT 10
            ''')
            stats['recently_modified'] = [
                {'url': url, 'title': title, 'last_modified': last_modified, 'version': version}
                for url, title, last_modified, version in cursor.fetchall()
            ]
            
            return stats
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des statistiques: {str(e)}")
            return {'error': str(e)}
            
        finally:
            if conn:
                conn.close()
    
    def get_all_tracked_urls(self) -> List[str]:
        """
        Récupère toutes les URLs suivies dans la base de données
        
        Returns:
            Liste des URLs
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT url FROM content_history')
            return [row[0] for row in cursor.fetchall()]
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des URLs: {str(e)}")
            return []
            
        finally:
            if conn:
                conn.close()
    
    def generate_change_report(self, start_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Génère un rapport sur les changements depuis une date spécifique
        
        Args:
            start_date: Date de début au format ISO (optionnel)
            
        Returns:
            Rapport des changements
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if start_date:
                cursor.execute('''
                    SELECT url, title, last_modified, version, type, category
                    FROM content_history
                    WHERE last_modified >= ?
                    ORDER BY last_modified DESC
                ''', (start_date,))
            else:
                # Par défaut, les 30 derniers jours
                thirty_days_ago = (datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - 
                              datetime.timedelta(days=30)).isoformat()
                cursor.execute('''
                    SELECT url, title, last_modified, version, type, category
                    FROM content_history
                    WHERE last_modified >= ?
                    ORDER BY last_modified DESC
                ''', (thirty_days_ago,))
            
            changes = []
            for url, title, last_modified, version, type_, category in cursor.fetchall():
                # Récupérer l'historique des versions pour cette URL
                cursor.execute('''
                    SELECT version, timestamp
                    FROM content_versions
                    WHERE url = ?
                    ORDER BY version DESC
                ''', (url,))
                
                versions = [{'version': v, 'timestamp': ts} for v, ts in cursor.fetchall()]
                
                changes.append({
                    'url': url,
                    'title': title,
                    'last_modified': last_modified,
                    'current_version': version,
                    'type': type_,
                    'category': category,
                    'version_history': versions
                })
            
            return {
                'period_start': start_date,
                'generated_at': datetime.now().isoformat(),
                'total_changes': len(changes),
                'changes': changes
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération du rapport de changements: {str(e)}")
            return {'error': str(e)}
            
        finally:
            if conn:
                conn.close()
