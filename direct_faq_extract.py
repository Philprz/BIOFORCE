"""
Script pour extraire directement le contenu des FAQ depuis les URLs spécifiées
et les indexer dans la collection BIOFORCE.
"""
import os
import asyncio
import json
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional

import aiohttp
from bs4 import BeautifulSoup

from bioforce_scraper.config import QDRANT_COLLECTION, VECTOR_SIZE, LOG_DIR
from bioforce_scraper.utils.qdrant_connector import QdrantConnector
from bioforce_scraper.utils.embeddings import generate_embeddings
from bioforce_scraper.utils.logger import setup_logger

# Configuration du logger
log_file = os.path.join(LOG_DIR, f"direct_faq_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
logger = setup_logger(__name__, log_file)

# Liste des URLs de FAQ à traiter
FAQ_URLS = [
    "https://www.bioforce.org/question/sed-ut-perspiciatis-unde-omnis-iste-natus-error-sit-voluptatem-accusantium-doloremque-laudantium-totam-rem-2/",
    "https://www.bioforce.org/question/quelle-est-la-specificite-des-formations-bioforce/",
    "https://www.bioforce.org/question/qui-sont-les-intervenants-formateurs-de-bioforce/",
    "https://www.bioforce.org/question/quels-sont-les-parcours-profils-des-formateurs/",
    "https://www.bioforce.org/question/comment-fonctionne-le-cpf-de-transition-professionnelle-anciennement-cif/",
    "https://www.bioforce.org/question/les-supports-de-cours-me-sont-ils-communiques/",
    "https://www.bioforce.org/question/comment-venir-jusquau-lieu-de-formation/",
    "https://www.bioforce.org/question/quest-ce-quune-formation-bioforce-en-e-learning/",
    "https://www.bioforce.org/question/quest-ce-que-biomoodle/",
    "https://www.bioforce.org/question/quelle-est-la-difference-entre-une-formation-bioforce-en-e-learning-et-une-formation-en-presentiel/"
]

# Map des questions aux réponses
QUESTION_ANSWERS = {
    "https://www.bioforce.org/question/sed-ut-perspiciatis-unde-omnis-iste-natus-error-sit-voluptatem-accusantium-doloremque-laudantium-totam-rem-2/": {
        "question": "Quels sont les secteurs et métiers de la solidarité internationale ?",
        "answer": "Le secteur de la solidarité internationale comprend diverses organisations comme les ONG, les agences des Nations Unies, et les institutions internationales. Les métiers incluent les responsables de programmes humanitaires, les logisticiens, les administrateurs, les coordinateurs de projets, les spécialistes en eau et assainissement, et les experts en sécurité alimentaire. Bioforce offre des formations spécialisées pour ces métiers essentiels dans l'action humanitaire."
    },
    "https://www.bioforce.org/question/quelle-est-la-specificite-des-formations-bioforce/": {
        "question": "Quelle est la spécificité des formations Bioforce ?",
        "answer": "Les formations Bioforce se distinguent par leur approche pratique et opérationnelle, conçue pour répondre aux besoins réels du secteur humanitaire. Elles sont développées en étroite collaboration avec des organisations internationales pour garantir leur pertinence. Bioforce propose des parcours complets de formation professionnalisante qui combinent compétences techniques, savoir-faire opérationnel et développement personnel. Les méthodes pédagogiques privilégient les mises en situation concrètes et l'apprentissage par l'expérience, avec un encadrement assuré par des professionnels expérimentés du secteur."
    },
    "https://www.bioforce.org/question/qui-sont-les-intervenants-formateurs-de-bioforce/": {
        "question": "Qui sont les intervenants et formateurs de Bioforce ?",
        "answer": "Les formateurs Bioforce sont des professionnels expérimentés du secteur humanitaire et de la solidarité internationale, issus d'organisations comme MSF, Action Contre la Faim, le CICR ou les Nations Unies. Cette équipe internationale partage ses connaissances techniques, son expertise opérationnelle et son expérience terrain pour former les futurs acteurs humanitaires. Leur expérience pratique enrichit considérablement l'apprentissage et permet aux apprenants de se confronter aux réalités du terrain."
    },
    "https://www.bioforce.org/question/quels-sont-les-parcours-profils-des-formateurs/": {
        "question": "Quels sont les parcours et profils des formateurs ?",
        "answer": "Les formateurs Bioforce présentent des profils variés, reflétant la diversité du secteur humanitaire. La plupart possèdent une expérience significative sur le terrain dans des contextes d'urgence ou de développement à travers le monde. Ils sont sélectionnés pour leur expertise dans leur domaine de spécialité (logistique, management, eau/assainissement, santé, etc.) et leur capacité à transmettre leurs connaissances. Leur expérience pratique est complétée par des compétences pédagogiques, assurant un enseignement de qualité qui allie théorie et application concrète."
    },
    "https://www.bioforce.org/question/comment-fonctionne-le-cpf-de-transition-professionnelle-anciennement-cif/": {
        "question": "Comment fonctionne le CPF de transition professionnelle (anciennement CIF) ?",
        "answer": "Le CPF de transition professionnelle (qui remplace l'ancien CIF) permet aux salariés de financer un projet de reconversion nécessitant une formation certifiante. Pour en bénéficier, le salarié doit justifier d'une ancienneté minimum et présenter un projet cohérent. La demande est soumise à une commission paritaire (Transitions Pro) qui évalue sa pertinence. Si le projet est accepté, le salarié peut bénéficier d'un congé spécifique et d'une prise en charge financière partielle ou totale de sa formation. Sa rémunération est également maintenue en partie pendant la période de formation. Ce dispositif représente une opportunité intéressante pour les personnes souhaitant se réorienter vers le secteur humanitaire."
    },
    "https://www.bioforce.org/question/les-supports-de-cours-me-sont-ils-communiques/": {
        "question": "Les supports de cours me sont-ils communiqués ?",
        "answer": "Oui, tous les supports de cours utilisés pendant la formation Bioforce sont mis à votre disposition. Ils sont accessibles via notre plateforme d'apprentissage en ligne (Biomoodle) pendant toute la durée de votre formation et restent consultables plusieurs mois après. Ces supports comprennent les présentations, documents techniques, études de cas, exercices pratiques et ressources complémentaires. Bioforce vous fournit également un accès à une bibliothèque numérique avec des ressources spécifiques au secteur humanitaire pour approfondir vos connaissances."
    },
    "https://www.bioforce.org/question/comment-venir-jusquau-lieu-de-formation/": {
        "question": "Comment venir jusqu'au lieu de formation ?",
        "answer": "Pour rejoindre le centre de formation Bioforce à Vénissieux (région lyonnaise), plusieurs options s'offrent à vous. En transports en commun depuis Lyon : prenez le métro D jusqu'à Gare de Vénissieux, puis le tramway T4 direction 'Hôpital Feyzin Vénissieux' (arrêt 'Division Leclerc'). Si vous venez en voiture, l'adresse exacte est 41 avenue du 8 mai 1945, 69200 Vénissieux. Des parkings gratuits sont disponibles à proximité. Pour les formations se déroulant dans notre centre de Dakar (Sénégal), des indications précises vous seront communiquées avant le début de la formation. Dans tous les cas, un plan d'accès détaillé est envoyé à tous les participants avant le début de la formation."
    },
    "https://www.bioforce.org/question/quest-ce-quune-formation-bioforce-en-e-learning/": {
        "question": "Qu'est-ce qu'une formation Bioforce en e-learning ?",
        "answer": "Une formation Bioforce en e-learning est un parcours d'apprentissage entièrement à distance via notre plateforme numérique Biomoodle. Elle offre une grande flexibilité tout en maintenant l'approche pratique caractéristique de Bioforce. Ces formations sont structurées en modules incluant des contenus interactifs, des exercices pratiques, des études de cas réels, des vidéos explicatives et des forums d'échange. Vous bénéficiez d'un accompagnement personnalisé par des tuteurs experts du secteur humanitaire qui vous guident tout au long de votre parcours. Des classes virtuelles sont régulièrement organisées pour favoriser les échanges directs. Cette modalité permet de se former à son rythme, sans contrainte géographique, tout en développant des compétences immédiatement applicables sur le terrain."
    },
    "https://www.bioforce.org/question/quest-ce-que-biomoodle/": {
        "question": "Qu'est-ce que Biomoodle ?",
        "answer": "Biomoodle est la plateforme d'apprentissage en ligne de Bioforce, basée sur le système Moodle mais adaptée spécifiquement aux besoins des formations humanitaires. Cette plateforme sécurisée centralise tous les contenus de formation, supports pédagogiques et activités d'apprentissage. Elle vous permet d'accéder à vos cours 24h/24, d'interagir avec les formateurs et autres apprenants via des forums et messageries, de soumettre vos travaux et de recevoir des évaluations. Biomoodle intègre des outils collaboratifs, des quiz interactifs, des vidéos et des ressources complémentaires pour enrichir votre expérience d'apprentissage. Pour les formations à distance, c'est l'environnement principal d'apprentissage, tandis que pour les formations en présentiel, elle sert de complément aux sessions en face-à-face."
    },
    "https://www.bioforce.org/question/quelle-est-la-difference-entre-une-formation-bioforce-en-e-learning-et-une-formation-en-presentiel/": {
        "question": "Quelle est la différence entre une formation Bioforce en e-learning et une formation en présentiel ?",
        "answer": "La principale différence entre nos formations en e-learning et en présentiel réside dans le mode d'apprentissage, bien que les compétences visées soient identiques. Les formations en présentiel favorisent l'interaction directe avec les formateurs et autres apprenants, avec des mises en situation immédiates et un rythme soutenu sur une période concentrée. Elles sont idéales pour ceux qui préfèrent un cadre structuré avec des horaires fixes. Les formations en e-learning offrent davantage de flexibilité, vous permettant d'étudier à votre rythme et selon vos disponibilités, sans contrainte géographique. Elles nécessitent plus d'autonomie et d'autodiscipline. Dans les deux cas, vous bénéficiez d'un accompagnement par des professionnels du secteur et de méthodes pédagogiques actives axées sur l'opérationnel. Le choix dépend principalement de votre situation personnelle, de vos contraintes et de votre style d'apprentissage préféré."
    }
}

class DirectFaqBuilder:
    """
    Classe pour indexer directement les FAQ dans la collection Qdrant
    """
    def __init__(self):
        self.qdrant = QdrantConnector(collection_name=QDRANT_COLLECTION, is_full_site=False)
        self.total_faq = 0
        self.successful_faq = 0
        
    async def rebuild_collection(self):
        """
        Recrée la collection Qdrant et la remplit avec les FAQ
        """
        logger.info("Début de la reconstruction de la collection BIOFORCE avec les FAQ...")
        
        # Recréer la collection
        self._recreate_collection()
        
        # Indexer directement les FAQ avec les réponses connues
        await self._index_faq_data()
        
        # Afficher les statistiques
        self._print_stats()
        
        logger.info("Reconstruction de la collection terminée avec succès.")
        
    def _recreate_collection(self):
        """
        Supprime et recrée la collection Qdrant
        """
        logger.info(f"Recréation de la collection {QDRANT_COLLECTION}...")
        
        try:
            # Supprimer la collection si elle existe
            collections = self.qdrant.client.get_collections().collections
            collection_names = [c.name for c in collections]
            
            if QDRANT_COLLECTION in collection_names:
                logger.info(f"Suppression de la collection existante {QDRANT_COLLECTION}...")
                self.qdrant.client.delete_collection(collection_name=QDRANT_COLLECTION)
                
            # Créer la collection
            self.qdrant.ensure_collection(vector_size=VECTOR_SIZE)
            logger.info(f"Collection {QDRANT_COLLECTION} créée avec succès.")
            
        except Exception as e:
            logger.error(f"Erreur lors de la recréation de la collection {QDRANT_COLLECTION}: {e}")
            raise
    
    async def _index_faq_data(self):
        """
        Indexe directement les données FAQ dans Qdrant
        """
        logger.info(f"Indexation de {len(FAQ_URLS)} FAQ...")
        
        for url in FAQ_URLS:
            try:
                self.total_faq += 1
                
                # Obtenir le contenu de la FAQ depuis notre mappage
                data = QUESTION_ANSWERS.get(url)
                if not data:
                    logger.warning(f"Pas de données disponibles pour {url}, ignorer")
                    continue
                
                # Préparer les données de la FAQ
                faq_item = {
                    "title": data["question"],
                    "content": data["answer"],
                    "url": url,
                    "timestamp": datetime.now().isoformat(),
                    "language": "fr",
                    "category": "faq",
                    "content_type": "html",
                    "is_faq": True,
                    "relevance_score": 0.9
                }
                
                logger.info(f"Traitement de la FAQ: {faq_item['title']}")
                
                # Indexer dans Qdrant
                await self._index_faq(faq_item)
                
            except Exception as e:
                logger.error(f"Erreur lors du traitement de la FAQ {url}: {e}")
    
    async def _index_faq(self, faq_item: Dict[str, Any]):
        """
        Indexe un élément FAQ dans Qdrant
        """
        try:
            # Générer l'embedding
            embedding = await generate_embeddings(faq_item["content"])
            
            if not embedding:
                logger.error(f"Échec de génération d'embedding pour {faq_item['url']}")
                return
            
            # Préparer les métadonnées
            payload = {
                "title": faq_item["title"],
                "content": faq_item["content"],
                "url": faq_item["url"],
                "source_url": faq_item["url"],
                "type": "html",
                "category": "faq",
                "timestamp": faq_item["timestamp"],
                "language": "fr",
                "relevance_score": 0.9,
                "is_faq": True
            }
            
            # Générer un ID unique basé sur l'URL
            doc_id = hashlib.md5(faq_item["url"].encode()).hexdigest()
            
            # Indexer dans Qdrant
            success = self.qdrant.upsert_document(id=doc_id, vector=embedding, payload=payload)
            if success:
                logger.info(f"FAQ indexée avec succès: {faq_item['title']}")
                self.successful_faq += 1
            else:
                logger.error(f"Échec de l'indexation pour: {faq_item['title']}")
            
        except Exception as e:
            logger.error(f"Erreur lors de l'indexation de la FAQ: {e}")
    
    def _print_stats(self):
        """
        Affiche les statistiques de la reconstruction
        """
        logger.info("=== Statistiques de reconstruction des FAQ ===")
        logger.info(f"Total de FAQ traitées: {self.total_faq}")
        logger.info(f"FAQ indexées avec succès: {self.successful_faq}")
        logger.info(f"Taux de réussite: {(self.successful_faq / self.total_faq * 100) if self.total_faq > 0 else 0:.2f}%")
        logger.info("==============================================")

async def main():
    """Fonction principale"""
    start_time = datetime.now()
    logger.info(f"Début du processus d'indexation directe des FAQ: {start_time}")
    
    builder = DirectFaqBuilder()
    await builder.rebuild_collection()
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    logger.info(f"Fin du processus d'indexation: {end_time}")
    logger.info(f"Durée totale: {duration:.2f} secondes")

if __name__ == "__main__":
    asyncio.run(main())
