# Bioforce Admin

Interface d'administration pour le chatbot Bioforce. Cette interface permet aux administrateurs de gérer le chatbot, de mettre à jour la base de connaissances et d'effectuer des opérations de maintenance.

## Fonctionnalités

- Tableau de bord avec informations système
- Gestion des mises à jour GitHub
- Lancement des opérations de scraping (FAQ et site complet)
- Surveillance de la base de connaissances Qdrant
- Visualisation des logs système

## Déploiement sur Render

1. Créez un nouveau service de type "Static Site" sur Render
2. Nom suggéré : `Bioforce-admin`
3. GitHub repo : URL de votre dépôt GitHub contenant ces fichiers
4. Branch : `main`
5. Build command : `echo "Build completed"`
6. Publish directory : `/bioforce-admin` (suivant le même modèle que demo_interface)

## Configuration

Le fichier `admin.js` est configuré pour pointer vers l'API Bioforce en production. Pour le développement local :

1. Ouvrez `admin.js`
2. Commentez la ligne : `const API_BASE_URL = "https://bioforce.onrender.com";`
3. Décommentez la ligne : `// const API_BASE_URL = window.location.origin;`

## CORS

Assurez-vous que l'API Bioforce autorise les requêtes CORS depuis le domaine du site d'administration.
