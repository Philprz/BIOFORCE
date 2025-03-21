# BioforceBot API

API pour le chatbot d'assistance aux candidats Bioforce basée sur FastAPI et OpenAI.

## Fonctionnalités

- Chatbot RAG (Retrieval-Augmented Generation) qui utilise la FAQ Bioforce comme base de connaissances
- Recherche vectorielle avec Qdrant pour trouver des informations pertinentes
- Génération de réponses avec OpenAI GPT-4o-mini
- API RESTful avec documentation interactive
- **Nouvelles fonctionnalités:**
  - Scraping automatique hebdomadaire de la FAQ Bioforce
  - Scraping du site complet Bioforce avec extraction de contenu pertinent
  - Système de rappels pour les candidats inactifs
  - Interface utilisateur améliorée avec fenêtre redimensionnable
  - Orchestration centralisée via un planificateur

## Architecture

- **Backend**: FastAPI (Python)
- **Base de connaissances**: Qdrant (base de données vectorielle)
- **LLM**: OpenAI GPT-4o-mini
- **Scraping**: Playwright
- **Planification**: APScheduler
- **Déploiement**: Render

## Modules du projet

- **bioforce_scraper/faq_scraper.py**: Scraper spécialisé pour la FAQ
- **bioforce_scraper/main.py**: Scraper principal pour le site complet
- **bioforce_scraper/scheduler.py**: Planificateur des tâches automatiques
- **bioforce_scraper/utils/reminder_service.py**: Service de rappels pour les candidats
- **bioforce_scraper/utils/qdrant_connector.py**: Connecteur pour la base de données vectorielle
- **bioforce_scraper/utils/embeddings.py**: Génération des embeddings pour la recherche
- **bioforce_scraper/api/app.py**: API FastAPI pour le chatbot
- **bioforcebot.js**: Interface utilisateur du chatbot

## Endpoints API

- `/query`: Interrogation de la base de connaissances
- `/scrape/faq`: Déclenchement manuel du scraping de la FAQ
- `/scrape/full`: Déclenchement manuel du scraping du site complet
- `/reminder/send`: Envoi manuel de rappels
- `/scheduler/status`: Vérification du statut du planificateur
- `/scheduler/run/{job_id}`: Déclenchement manuel d'une tâche planifiée
- `/qdrant/stats`: Statistiques de la base de connaissances
- `/health`: Vérification de l'état de l'API

## Variables d'environnement requises

```
OPENAI_API_KEY=votre_clé_api_openai
QDRANT_URL=votre_url_qdrant
QDRANT_API_KEY=votre_clé_api_qdrant
SCHEDULER_ENABLED=true
REMINDER_ENABLED=true
```

## Déploiement sur Render

1. Créez un nouveau Web Service sur Render
2. Connectez votre dépôt Git
3. Configurez les variables d'environnement dans la section "Environment"
4. Utilisez les paramètres suivants:
   - **Runtime**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn -k uvicorn.workers.UvicornWorker bioforce_scraper.api.app:app`

## Développement local

1. Clonez le dépôt
2. Créez et activez un environnement virtuel
3. Installez les dépendances: `pip install -r requirements.txt`
4. Créez un fichier `.env` avec les variables d'environnement requises
5. Lancez l'application API: `uvicorn bioforce_scraper.api.app:app --reload`
6. Pour exécuter manuellement le scraper de FAQ: `python -m bioforce_scraper.faq_scraper`
7. Pour exécuter le planificateur: `python -m bioforce_scraper.scheduler`

## Documentation API

Lorsque l'application est en cours d'exécution, la documentation Swagger est disponible à l'URL `/docs`.

## Fonctionnement du planificateur

Le planificateur exécute par défaut les tâches suivantes:
- Mise à jour de la FAQ: tous les lundis à 01h00
- Mise à jour du site complet: tous les mercredis à 02h00
- Envoi de rappels: toutes les 5 minutes pour les utilisateurs actifs

Ces paramètres sont configurables dans le fichier `config.py`.

## Dépannage de la connexion à Qdrant

Si vous rencontrez des problèmes de connexion avec Qdrant, voici les étapes à suivre pour diagnostiquer et résoudre les problèmes :

### Vérification des variables d'environnement

Assurez-vous que les variables d'environnement suivantes sont correctement définies dans votre fichier `.env` :

```
QDRANT_URL=https://votre-instance.qdrant.io:6333
QDRANT_API_KEY=votre_clé_api_qdrant
QDRANT_COLLECTION=BIOFORCE
```

### Tests de diagnostic

Nous avons inclus plusieurs scripts de test pour vérifier la connexion à Qdrant :

1. **Test rapide de connexion à Qdrant** :
   ```
   python test_qdrant.py
   ```
   Ce script vérifie simplement si la connexion à Qdrant peut être établie.

2. **Test de recherche dans Qdrant** :
   ```
   python test_qdrant_search.py
   ```
   Ce script effectue une recherche de test dans la collection Qdrant.

3. **Test du chatbot avec Qdrant** :
   ```
   python test_chatbot.py
   ```
   Ce script teste le chatbot complet, y compris la connexion à Qdrant et la génération de réponses.

4. **Test complet du système** :
   ```
   python test_full_system.py -v
   ```
   Ce script exécute une série de tests sur tous les composants du système. L'option `-v` active le mode verbeux pour plus de détails.

### Erreurs courantes

- **Erreur de connexion réseau** : Vérifiez que votre instance Qdrant est accessible depuis votre réseau actuel.
- **Erreur d'authentification** : Vérifiez que votre clé API Qdrant est correcte.
- **Collection non trouvée** : Vérifiez que le nom de collection spécifié existe dans votre instance Qdrant.
- **Erreur de format de vecteur** : Assurez-vous que la dimension des vecteurs générés correspond à celle attendue par Qdrant.

### Vérification de l'état du service

Vous pouvez vérifier l'état du service en accédant à l'URL `/admin/status` de l'API. Cette page affiche le statut de tous les composants, y compris la connexion à Qdrant.

## Journalisation

Le système utilise le module de journalisation standard de Python. Les logs sont affichés dans la console et peuvent être configurés pour être enregistrés dans un fichier.

Pour augmenter le niveau de détail des logs, modifiez le niveau de journalisation dans le fichier `bioforce_api_chatbot.py` :

```python
logging.basicConfig(level=logging.DEBUG, ...)
```

Les niveaux disponibles sont : DEBUG, INFO, WARNING, ERROR, CRITICAL.