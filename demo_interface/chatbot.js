// Configuration de l'API
// Forcé pour utiliser uniquement l'API locale
const API_LOCAL = 'http://localhost:8000'; 
const API_PRODUCTION = 'https://bioforce-interface.onrender.com';  // URL de l'interface
const ADMIN_PRODUCTION = 'https://bioforce-admin.onrender.com';    // URL de l'admin
const USE_CORS_PROXY = false; // Désactivé car nous utilisons l'API locale
const CORS_PROXY = 'https://corsproxy.io/?';  // Proxy CORS fiable

// SOLUTION D'URGENCE: Forcer l'utilisation de l'API locale
const USE_PRODUCTION_API = false; // Force mode local
const USE_LOCAL_API = true;      // Active l'API locale
const USE_SIMULATION_FALLBACK = true; // Mode simulation uniquement comme fallback
const FORCE_SIMULATION_MODE = false;  // Désactive le mode simulation forcé

// Détection automatique de l'environnement
// const USE_PRODUCTION_API = window.location.hostname.includes('render.com'); 

// URL finale avec proxy CORS si nécessaire
const API_URL = USE_PRODUCTION_API 
    ? (USE_CORS_PROXY ? CORS_PROXY + encodeURIComponent(API_PRODUCTION) : API_PRODUCTION) 
    : API_LOCAL;

const ADMIN_URL = USE_PRODUCTION_API ? ADMIN_PRODUCTION : `${API_LOCAL}/admin`;

// Configuration de l'administration
const ADMIN_PASSWORD = "bioforce2025"; // Mot de passe pour l'accès admin

// Mots-clés associés aux questions de candidature/admission
const FORMATION_KEYWORDS = [
    "formation", "étudier", "apprendre", "cours", "programme", 
    "devenir", "métier", "carrière", "humanitaire", "diplôme"
];

const ORIENTATION_KEYWORDS = [
    "orientation", "test", "choix", "carrière", "métier", "convient", 
    "profil", "compétence", "aptitude"
];

// Éléments DOM
const chatWidget = document.getElementById('chatbot-widget');
const chatHeader = chatWidget.querySelector('.chat-header');
const chatMessages = document.getElementById('chat-messages');
const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-message');
const minimizeButton = document.getElementById('minimize-chat');
const adminButton = document.getElementById('admin-btn');

// Éléments de la boîte de dialogue admin
const adminOverlay = document.getElementById('admin-overlay');
const adminDialog = document.getElementById('admin-dialog');
const adminPassword = document.getElementById('admin-password');
const cancelAdminBtn = document.getElementById('cancel-admin');
const loginAdminBtn = document.getElementById('login-admin');

// Variables globales
let isDragging = false;
let dragOffsetX, dragOffsetY;

// Récupérer la position du chatbot stockée dans localStorage (si elle existe)
const savedPosition = JSON.parse(localStorage.getItem('chatbotPosition'));
if (savedPosition) {
    // Appliquer la position sauvegardée
    chatWidget.style.right = 'auto';
    chatWidget.style.left = savedPosition.left + 'px';
    chatWidget.style.top = savedPosition.top + 'px';
    chatWidget.style.bottom = 'auto';
}

// Événements pour la manipulation du chatbot
chatHeader.addEventListener('mousedown', startDrag);
document.addEventListener('mousemove', dragChatbot);
document.addEventListener('mouseup', stopDrag);

// Pour la compatibilité mobile
chatHeader.addEventListener('touchstart', handleTouchStart, {passive: false});
document.addEventListener('touchmove', handleTouchMove, {passive: false});
document.addEventListener('touchend', handleTouchEnd);

// Fonction pour commencer le déplacement
function startDrag(e) {
    // Ne pas commencer le déplacement si on clique sur un bouton
    if (e.target === minimizeButton || e.target === adminButton || 
        e.target.closest('#minimize-chat') || e.target.closest('#admin-btn')) {
        return;
    }

    isDragging = true;
    chatWidget.classList.add('dragging');
    
    // Calculer le décalage entre le clic et la position du chatbot
    const rect = chatWidget.getBoundingClientRect();
    
    if (e.type === 'mousedown') {
        dragOffsetX = e.clientX - rect.left;
        dragOffsetY = e.clientY - rect.top;
    } else if (e.type === 'touchstart') {
        dragOffsetX = e.touches[0].clientX - rect.left;
        dragOffsetY = e.touches[0].clientY - rect.top;
    }
    
    // Empêcher le texte d'être sélectionné pendant le déplacement
    e.preventDefault();
}

// Fonction pour déplacer le chatbot
function dragChatbot(e) {
    if (!isDragging) return;
    
    let clientX, clientY;
    
    if (e.type === 'mousemove') {
        clientX = e.clientX;
        clientY = e.clientY;
    } else if (e.type === 'touchmove') {
        clientX = e.touches[0].clientX;
        clientY = e.touches[0].clientY;
        e.preventDefault(); // Empêcher le défilement de la page
    }
    
    // Nouvelle position
    let left = clientX - dragOffsetX;
    let top = clientY - dragOffsetY;
    
    // Limites pour ne pas sortir de la fenêtre
    const maxX = window.innerWidth - chatWidget.offsetWidth;
    const maxY = window.innerHeight - chatWidget.offsetHeight;
    
    left = Math.max(0, Math.min(maxX, left));
    top = Math.max(0, Math.min(maxY, top));
    
    // Appliquer la nouvelle position
    chatWidget.style.left = left + 'px';
    chatWidget.style.top = top + 'px';
    chatWidget.style.right = 'auto';
    chatWidget.style.bottom = 'auto';
}

// Fonction pour arrêter le déplacement
function stopDrag() {
    if (isDragging) {
        isDragging = false;
        chatWidget.classList.remove('dragging');
        
        // Sauvegarder la position dans localStorage
        const position = {
            left: parseInt(chatWidget.style.left),
            top: parseInt(chatWidget.style.top)
        };
        localStorage.setItem('chatbotPosition', JSON.stringify(position));
    }
}

// Gestionnaires d'événements tactiles
function handleTouchStart(e) {
    // Ne pas déclencher le déplacement si on touche les boutons
    if (e.target === minimizeButton || e.target === adminButton || 
        e.target.closest('#minimize-chat') || e.target.closest('#admin-btn')) {
        return;
    }
    startDrag(e);
}

function handleTouchMove(e) {
    dragChatbot(e);
}

function handleTouchEnd() {
    stopDrag();
}

// État du chat
let chatHistory = [];
let userId = 'demo-user-' + Math.floor(Math.random() * 1000);

// Fonction pour ajouter un message au chat
function addMessageToChat(message, sender) {
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', sender);
    
    // Amélioration de la mise en forme pour une meilleure lisibilité
    let formattedMessage = message;
    
    // Gérer les listes (puces avec astérisques)
    if (message.includes('**')) {
        // Remplacer les marqueurs markdown par du HTML
        formattedMessage = formattedMessage
            // Titres en gras
            .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
            // Remplacer les puces avec étoiles par des listes HTML
            .replace(/\n\*\*([^*]+)\*\*/g, '<br><br><strong>$1</strong>');
            
        // Si le message contient des listes, on transforme en HTML propre
        if (formattedMessage.includes('<br><strong>')) {
            const parts = formattedMessage.split('<br><br>');
            const intro = parts.shift(); // Première partie du message
            
            if (parts.length > 0) {
                formattedMessage = `
                    <p>${intro}</p>
                    <ul>
                        ${parts.map(item => `<li>${item}</li>`).join('')}
                    </ul>
                `;
            }
        }
    }
    
    // Formatage des sauts de ligne
    formattedMessage = formattedMessage
        .replace(/\n\n/g, '<br><br>')
        .replace(/\n/g, '<br>');
    
    messageDiv.innerHTML = `<p>${formattedMessage}</p>`;
    chatMessages.appendChild(messageDiv);
    
    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    // Update chat history
    chatHistory.push({
        role: sender === 'user' ? 'user' : 'assistant',
        content: message
    });
}

// Vérification de la connectivité API au chargement
window.addEventListener('DOMContentLoaded', async () => {
    try {
        console.log('Test de connectivité API...');
        const testResponse = await fetch(`${API_URL}/`, {
            method: 'GET',
            mode: 'cors',
            headers: { 'Accept': 'application/json' }
        });
        
        if (testResponse.ok) {
            console.log('API connectée avec succès :', await testResponse.json());
        } else {
            console.warn('API accessible mais retourne une erreur :', testResponse.status);
        }
    } catch (error) {
        console.error('API inaccessible :', error);
        console.log('Le mode simulation sera utilisé automatiquement.');
    }
});

/**
 * Fonction pour gérer les commandes spéciales
 * @param {string} message - Le message utilisateur
 * @returns {boolean} - True si une commande a été traitée
 */
function handleSpecialCommands(message) {
    // Commande d'administration via message
    if (message.trim() === '*Admin*') {
        // Ouvrir la boîte de dialogue d'authentification
        showAdminDialog();
        addMessageToChat("Veuillez vous authentifier pour accéder à l'interface d'administration.", 'bot');
        return true;
    }
    return false;
}

/**
 * Fonction pour détecter si le message concerne les formations
 * @param {string} message - Le message utilisateur
 * @returns {boolean} - True si le message concerne les formations
 */
function isFormationRelated(message) {
    const messageLower = message.toLowerCase();
    return FORMATION_KEYWORDS.some(keyword => messageLower.includes(keyword.toLowerCase()));
}

/**
 * Fonction pour détecter si le message concerne l'orientation
 * @param {string} message - Le message utilisateur
 * @returns {boolean} - True si le message concerne l'orientation
 */
function isOrientationRelated(message) {
    const messageLower = message.toLowerCase();
    return ORIENTATION_KEYWORDS.some(keyword => messageLower.includes(keyword.toLowerCase()));
}

// Fonction pour envoyer un message à l'API
async function sendMessageToAPI(userMessage) {
    // Vérifier s'il s'agit d'une commande spéciale
    if (handleSpecialCommands(userMessage)) {
        return;
    }
    
    // SOLUTION D'URGENCE: Si le mode simulation forcé est activé, utiliser directement la simulation
    if (FORCE_SIMULATION_MODE) {
        console.log('SOLUTION D\'URGENCE: Mode simulation forcé activé');
        simulateAPIResponse(userMessage);
        return;
    }
    
    try {
        console.log('Tentative de connexion à l\'API:', API_URL);
        console.log('Mode API:', USE_PRODUCTION_API ? 'Production' : 'Local');
        
        // Ajouter indication de chargement
        const loadingDiv = document.createElement('div');
        loadingDiv.classList.add('message', 'bot', 'loading');
        loadingDiv.innerHTML = '<p>...</p>';
        chatMessages.appendChild(loadingDiv);
        
        // Construction du message au format attendu par l'API
        const formattedMessages = chatHistory.map(msg => ({
            role: msg.role,
            content: msg.content
        }));
        
        const requestData = {
            user_id: userId,
            messages: formattedMessages,
            context: {
                page: window.location.pathname,
                candidature_id: '00080932'
            }
        };
        
        console.log('Données envoyées à l\'API:', JSON.stringify(requestData));
        
        let apiSuccess = false;
        let apiResponse = null;
        
        try {
            // Essayer de contacter l'API avec un timeout
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 5000); // 5 secondes de timeout
            
            const fetchOptions = {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData),
                signal: controller.signal
            };
            
            console.log('Envoi de la requête fetch...');
            const response = await fetch(`${API_URL}/chat`, fetchOptions);
            clearTimeout(timeoutId);
            
            console.log('Réponse reçue, statut:', response.status);
            
            if (response.ok) {
                const data = await response.json();
                console.log('Réponse API (données JSON):', data);
                apiResponse = data;
                apiSuccess = true;
            } else {
                console.error('Erreur API:', response.status, response.statusText);
                const errorText = await response.text();
                console.error('Détails de l\'erreur:', errorText);
                throw new Error(`Erreur serveur: ${response.status} ${response.statusText}`);
            }
        } catch (fetchError) {
            console.error('Erreur fetch:', fetchError);
            // On ne relance pas l'erreur, on laisse le code continuer
        }
        
        // Supprimer l'indication de chargement
        chatMessages.removeChild(loadingDiv);
        
        if (apiSuccess && apiResponse) {
            // Afficher la réponse du chatbot
            addMessageToChat(apiResponse.message.content, 'bot');
            
            // Ajouter des liens vers les sources si disponibles
            if (apiResponse.references && apiResponse.references.length > 0) {
                // Création d'un élément pour afficher les références/sources
                const sourcesDiv = document.createElement('div');
                sourcesDiv.classList.add('message', 'bot', 'sources');
                
                let sourcesContent = '<p><small>Sources pertinentes :</small></p><ul>';
                apiResponse.references.forEach(ref => {
                    if (ref.url) {
                        sourcesContent += `<li><a href="${ref.url}" target="_blank" class="source-link">${ref.question || ref.url}</a></li>`;
                    }
                });
                sourcesContent += '</ul>';
                
                sourcesDiv.innerHTML = sourcesContent;
                chatMessages.appendChild(sourcesDiv);
            }
            
            // Vérifier si le message concerne les formations ou l'orientation
            if (isFormationRelated(userMessage)) {
                // Suggestion pour page des formations
                const formationDiv = document.createElement('div');
                formationDiv.classList.add('message', 'bot', 'suggestion');
                formationDiv.innerHTML = `
                    <p>Pour explorer toutes nos formations, vous pouvez consulter notre page dédiée :</p>
                    <p><a href="https://www.bioforce.org/learn/formations-humanitaires/trouver-ma-formation/" target="_blank" class="suggestion-link">
                        Trouver ma formation humanitaire →
                    </a></p>
                `;
                chatMessages.appendChild(formationDiv);
            }
            
            if (isOrientationRelated(userMessage)) {
                // Suggestion pour le test d'orientation
                const orientationDiv = document.createElement('div');
                orientationDiv.classList.add('message', 'bot', 'suggestion');
                orientationDiv.innerHTML = `
                    <p>Vous vous interrogez sur votre orientation ? Découvrez notre test d'orientation :</p>
                    <p><a href="https://www.bioforce.org/learn/formations-humanitaires/preparer-mon-projet/test-dorientation/" target="_blank" class="suggestion-link">
                        Faire le test d'orientation →
                    </a></p>
                `;
                chatMessages.appendChild(orientationDiv);
            }
        } else if (USE_SIMULATION_FALLBACK) {
            console.log('Utilisation du mode simulation comme fallback');
            // Utiliser la simulation si l'API échoue
            simulateAPIResponse(userMessage);
        } else {
            // Gestion des erreurs
            const botResponse = "Désolé, je rencontre des difficultés à me connecter au serveur. Veuillez réessayer plus tard ou contacter l'équipe Bioforce directement.";
            addMessageToChat(botResponse, 'bot');
        }
        
    } catch (error) {
        console.error('Erreur générale:', error);
        
        if (USE_SIMULATION_FALLBACK) {
            console.log('Utilisation du mode simulation comme fallback après une erreur');
            // Utiliser la simulation si l'API échoue
            simulateAPIResponse(userMessage);
        } else {
            // Gestion des erreurs
            const botResponse = "Désolé, je rencontre des difficultés à me connecter au serveur. Veuillez réessayer plus tard ou contacter l'équipe Bioforce directement.";
            addMessageToChat(botResponse, 'bot');
        }
    }
}

// Fonction pour la simulation de réponse API (fallback)
function simulateAPIResponse(userMessage) {
    // Réponses prédéfinies pour la démo
    const responses = {
        "default": {
            content: "Je suis désolé, je n'ai pas trouvé d'information précise sur ce sujet. Vous pouvez consulter notre site web ou contacter directement notre équipe pour obtenir une réponse personnalisée.",
            source: "https://www.bioforce.org/contact/"
        },
        "formation": {
            content: "Bioforce propose plusieurs formations dans le domaine humanitaire, allant des métiers de support (logistique, RH, finances) aux métiers de coordination de projet. Nos formations sont reconnues par le secteur humanitaire international.",
            source: "https://www.bioforce.org/learn/formations-humanitaires/"
        },
        "logistique": {
            content: "La formation en logistique humanitaire de Bioforce vous prépare à gérer l'approvisionnement, le transport et le stockage des biens et équipements essentiels aux opérations humanitaires.",
            source: "https://www.bioforce.org/learn/formations-humanitaires/logistique-humanitaire/"
        },
        "financement": {
            content: "Plusieurs options de financement sont disponibles pour nos formations : bourses, prise en charge par Pôle Emploi, financement par des organismes de formation continue ou votre CPF.",
            source: "https://www.bioforce.org/learn/financer-ma-formation/"
        },
        "inscription": {
            content: "Les inscriptions se font en ligne sur notre site. Le processus comprend le dépôt d'un dossier de candidature, suivi d'un entretien de sélection pour évaluer votre motivation et votre projet professionnel.",
            source: "https://www.bioforce.org/learn/candidater/"
        }
    };
    
    // Recherche de mots-clés dans la question
    const messageLower = userMessage.toLowerCase();
    let bestMatch = "default";
    
    // Trouver la meilleure correspondance
    Object.keys(responses).forEach(key => {
        if (key !== "default" && messageLower.includes(key)) {
            bestMatch = key;
        }
    });
    
    // Simuler un délai de traitement
    setTimeout(() => {
        // Ajouter la réponse du chatbot
        addMessageToChat(responses[bestMatch].content, 'bot');
        
        // Ajouter un lien vers la source
        if (responses[bestMatch].source) {
            const sourceDiv = document.createElement('div');
            sourceDiv.classList.add('message', 'bot', 'source');
            sourceDiv.innerHTML = `
                <p><small>Pour plus d'informations, consultez :</small></p>
                <p><a href="${responses[bestMatch].source}" target="_blank" class="source-link">
                    ${responses[bestMatch].source.replace('https://www.bioforce.org/', '')} →
                </a></p>
            `;
            chatMessages.appendChild(sourceDiv);
        }
        
        // Vérifier si le message concerne les formations ou l'orientation (même pour les réponses simulées)
        if (isFormationRelated(userMessage)) {
            const formationDiv = document.createElement('div');
            formationDiv.classList.add('message', 'bot', 'suggestion');
            formationDiv.innerHTML = `
                <p>Pour explorer toutes nos formations, vous pouvez consulter notre page dédiée :</p>
                <p><a href="https://www.bioforce.org/learn/formations-humanitaires/trouver-ma-formation/" target="_blank" class="suggestion-link">
                    Trouver ma formation humanitaire →
                </a></p>
            `;
            chatMessages.appendChild(formationDiv);
        }
        
        if (isOrientationRelated(userMessage)) {
            const orientationDiv = document.createElement('div');
            orientationDiv.classList.add('message', 'bot', 'suggestion');
            orientationDiv.innerHTML = `
                <p>Vous vous interrogez sur votre orientation ? Découvrez notre test d'orientation :</p>
                <p><a href="https://www.bioforce.org/learn/formations-humanitaires/preparer-mon-projet/test-dorientation/" target="_blank" class="suggestion-link">
                    Faire le test d'orientation →
                </a></p>
            `;
            chatMessages.appendChild(orientationDiv);
        }
    }, 1000);
}

// Event Listeners
sendButton.addEventListener('click', () => {
    const message = userInput.value.trim();
    
    if (message) {
        // Ajouter le message de l'utilisateur au chat
        addMessageToChat(message, 'user');
        userInput.value = '';

        // Vérifier s'il s'agit d'une commande spéciale
        if (!handleSpecialCommands(message)) {
            // Envoyer le message à l'API
            sendMessageToAPI(message);
        }
    }
});

// Écouteur d'événement pour la touche Entrée
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendButton.click();
    }
});

// Écouteur d'événement pour le bouton de minimisation
minimizeButton.addEventListener('click', () => {
    // Basculer la visibilité du chatbot (minimiser/agrandir)
    const isMinimized = chatWidget.classList.toggle('minimized');
    
    // Mettre à jour le texte du bouton
    minimizeButton.textContent = isMinimized ? '+' : '−';
    
    // Sauvegarder l'état dans localStorage
    localStorage.setItem('chatbotMinimized', isMinimized);
});

// Fonctions pour l'administration
function showAdminDialog() {
    adminOverlay.style.display = 'block';
    adminDialog.style.display = 'block';
    adminPassword.value = '';
    adminPassword.focus();
}

function hideAdminDialog() {
    adminOverlay.style.display = 'none';
    adminDialog.style.display = 'none';
    adminPassword.value = '';
}

function checkAdminPassword() {
    const password = adminPassword.value.trim();
    
    if (password === ADMIN_PASSWORD) {
        hideAdminDialog();
        
        // Rediriger vers l'interface d'administration
        window.open(ADMIN_URL, '_blank');
        
        addMessageToChat("Authentification réussie. L'interface d'administration s'ouvre dans un nouvel onglet.", 'bot');
    } else {
        adminPassword.value = '';
        adminPassword.placeholder = 'Mot de passe incorrect';
        adminPassword.classList.add('error');
        
        setTimeout(() => {
            adminPassword.placeholder = 'Mot de passe';
            adminPassword.classList.remove('error');
        }, 2000);
    }
}

// Écouteurs d'événements pour l'administration
adminButton.addEventListener('click', showAdminDialog);
cancelAdminBtn.addEventListener('click', hideAdminDialog);
loginAdminBtn.addEventListener('click', checkAdminPassword);
adminPassword.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        checkAdminPassword();
    }
});
adminOverlay.addEventListener('click', hideAdminDialog);

// Restaurer l'état minimisé du chatbot (si sauvegardé)
if (localStorage.getItem('chatbotMinimized') === 'true') {
    chatWidget.classList.add('minimized');
    minimizeButton.textContent = '+';
}

// Initialisation
document.addEventListener('DOMContentLoaded', () => {
    // Message de bienvenue initial déjà dans le HTML
    
    // Mettre le focus sur l'input
    userInput.focus();
});
