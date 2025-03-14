# BioforceBot API

API pour le chatbot d'assistance aux candidats Bioforce basée sur FastAPI et OpenAI.

## Fonctionnalités

- Chatbot RAG (Retrieval-Augmented Generation) qui utilise la FAQ Bioforce comme base de connaissances
- Recherche vectorielle avec Qdrant pour trouver des informations pertinentes
- Génération de réponses avec OpenAI GPT-4o-mini
- API RESTful avec documentation interactive

## Architecture

- **Backend**: FastAPI (Python)
- **Base de connaissances**: Qdrant (base de données vectorielle)
- **LLM**: OpenAI GPT-4o-mini
- **Déploiement**: Render

## Endpoints API

- `/chat`: Endpoint principal du chatbot
- `/search`: Recherche directe dans la base de connaissances
- `/health`: Vérification de l'état de l'API

## Variables d'environnement requises

```
OPENAI_API_KEY=votre_clé_api_openai
QDRANT_URL=votre_url_qdrant
QDRANT_API_KEY=votre_clé_api_qdrant
```

## Déploiement sur Render

1. Créez un nouveau Web Service sur Render
2. Connectez votre dépôt Git
3. Configurez les variables d'environnement dans la section "Environment"
4. Utilisez les paramètres suivants:
   - **Runtime**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn -k uvicorn.workers.UvicornWorker bioforce_api_chatbot:app`

## Développement local

1. Clonez le dépôt
2. Créez et activez un environnement virtuel
3. Installez les dépendances: `pip install -r requirements.txt`
4. Créez un fichier `.env` avec les variables d'environnement requises
5. Lancez l'application: `uvicorn bioforce_api_chatbot:app --reload`

## Documentation API

Lorsque l'application est en cours d'exécution, la documentation Swagger est disponible à l'URL `/docs`.