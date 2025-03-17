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