# Interface de démonstration du chatbot Bioforce

Cette interface de démonstration permet de visualiser comment le chatbot Bioforce interagit avec les utilisateurs dans le contexte de l'espace candidature.

## Structure du projet

- `index.html` : Page d'accueil avec aperçu des candidatures
- `candidatures.html` : Liste des candidatures
- `dossier.html` : Détail d'un dossier de candidature
- `support.html` : Page de contact et support
- `faq.html` : Foire aux questions
- `styles.css` : Styles pour toutes les pages
- `chatbot.js` : Logique d'interaction du chatbot

## Fonctionnalités

1. **Interface répliquant l'espace candidature Bioforce**
   - Design fidèle à l'interface originale
   - Navigation entre les différentes pages

2. **Chatbot intégré**
   - Fenêtre de chat sur chaque page
   - Messages contextuels selon la page visitée
   - Mode démo avec réponses prédéfinies

3. **Intégration avec l'API**
   - Possibilité de basculer entre le mode démo et l'API réelle
   - Configuration simple via chatbot.js

## Comment exécuter la démo

1. Démarrez un serveur web local dans ce répertoire :
   ```
   python -m http.server 8080
   ```

2. Accédez à l'interface dans votre navigateur :
   ```
   http://localhost:8080
   ```

3. Pour connecter la démo à l'API réelle, modifiez dans `chatbot.js` :
   - Remplacez `simulateAPIResponse(message)` par `sendMessageToAPI(message)`
   - Assurez-vous que l'API FastAPI est en cours d'exécution à l'URL définie

## Points de démonstration

Pour démontrer efficacement le chatbot, voici quelques scénarios à montrer :

1. **Page d'accueil**
   - Le chatbot se présente et offre son aide

2. **Page candidatures**
   - Le chatbot détecte que l'utilisateur consulte ses candidatures et propose de l'aider

3. **Page dossier**
   - Le chatbot remarque les documents manquants et suggère des actions

4. **Page FAQ**
   - Le chatbot aide à trouver des informations spécifiques

5. **Page support**
   - Le chatbot propose des alternatives au formulaire de contact

## Personnalisation

Vous pouvez personnaliser les réponses prédéfinies du chatbot en mode démo en modifiant la fonction `simulateAPIResponse()` dans le fichier `chatbot.js`.
