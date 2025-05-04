/**
 * BioforceBot - Chatbot d'assistance aux candidats Bioforce
 * Version unifiée combinant chatbot.js et bioforcebot.js
 */

// Configuration de l'API et de l'environnement
const API_URL = window.location.origin;
const PRODUCTION_API = 'https://bioforce.onrender.com';
const ADMIN_URL = 'https://bioforce.onrender.com/admin'; // URL d'administration en dur pour éviter les problèmes de double slash

// Options de configuration
const CONFIG = {
    USE_SIMULATION_FALLBACK: true,  // Utiliser la simulation en cas d'échec de l'API
    DEBUG_MODE: false,              // Activer/désactiver les logs de débogage
    CACHE_ENABLED: true,            // Activer le cache des réponses
    CACHE_DURATION: 24 * 60 * 60    // Durée de validité du cache (en secondes)
};

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

// Cache pour les réponses
const responseCache = {};

// Éléments DOM
const chatWidget = document.getElementById('chatbot-widget');
const chatHeader = document.querySelector('.chat-header');
const chatMessages = document.getElementById('chat-messages');
const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-message');
const minimizeButton = document.getElementById('minimize-chat');
const adminButton = document.getElementById('admin-btn');

// Éléments de la boîte de dialogue admin (s'ils existent)
const adminOverlay = document.getElementById('admin-overlay');
const adminDialog = document.getElementById('admin-dialog');
const adminPassword = document.getElementById('admin-password');
const cancelAdminBtn = document.getElementById('cancel-admin');
const loginAdminBtn = document.getElementById('login-admin');

// Variables globales
let isDragging = false;
let dragOffsetX, dragOffsetY;
let chatHistory = [];
let userId = 'user-' + Math.floor(Math.random() * 10000);

/**
 * Fonctions utilitaires
 */

// Fonction pour les logs de débogage
function debug(message, data = null) {
    if (CONFIG.DEBUG_MODE) {
        if (data) {
            console.log(`[BioforceBot] ${message}`, data);
        } else {
            console.log(`[BioforceBot] ${message}`);
        }
    }
}

// Fonction pour générer une clé de cache
function generateCacheKey(message) {
    // Version simple: hash du message normalisé
    return btoa(message.toLowerCase().trim()).replace(/[^a-zA-Z0-9]/g, '');
}

// Fonction pour vérifier si deux messages sont similaires
function areMessagesSimilar(message1, message2, threshold = 0.7) {
    const words1 = new Set(message1.toLowerCase().split(/\s+/).filter(word => word.length > 3));
    const words2 = new Set(message2.toLowerCase().split(/\s+/).filter(word => word.length > 3));
    
    if (words1.size === 0 || words2.size === 0) return false;
    
    let commonCount = 0;
    for (const word of words1) {
        if (words2.has(word)) commonCount++;
    }
    
    const similarity = commonCount / Math.max(words1.size, words2.size);
    return similarity >= threshold;
}

// Trouver une réponse dans le cache
function findCachedResponse(message) {
    if (!CONFIG.CACHE_ENABLED) return null;
    
    const now = Date.now() / 1000; // Timestamp actuel en secondes
    const exactKey = generateCacheKey(message);
    
    // Vérifier la correspondance exacte
    if (responseCache[exactKey] && (now - responseCache[exactKey].timestamp < CONFIG.CACHE_DURATION)) {
        debug("Réponse trouvée dans le cache (correspondance exacte)");
        return responseCache[exactKey];
    }
    
    // Vérifier les correspondances similaires
    for (const key in responseCache) {
        const entry = responseCache[key];
        if (now - entry.timestamp < CONFIG.CACHE_DURATION) {
            if (areMessagesSimilar(message, entry.query)) {
                debug("Réponse trouvée dans le cache (correspondance similaire)");
                return entry;
            }
        }
    }
    
    return null;
}

// Ajouter une réponse au cache
function addToCache(query, response, references = []) {
    if (!CONFIG.CACHE_ENABLED) return;
    
    const key = generateCacheKey(query);
    responseCache[key] = {
        query: query,
        response: response,
        references: references,
        timestamp: Date.now() / 1000
    };
    
    debug("Réponse ajoutée au cache");
}

/**
 * Gestion des événements de déplacement du chatbot
 */

// Récupérer la position du chatbot stockée dans localStorage
const savedPosition = JSON.parse(localStorage.getItem('chatbotPosition'));
if (savedPosition) {
    chatWidget.style.right = 'auto';
    chatWidget.style.left = savedPosition.left + 'px';
    chatWidget.style.top = savedPosition.top + 'px';
    chatWidget.style.bottom = 'auto';
}

// Restaurer l'état minimisé du chatbot
if (localStorage.getItem('chatbotMinimized') === 'true') {
    chatWidget.classList.add('minimized');
    minimizeButton.textContent = '+';
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

/**
 * Fonctions de gestion des messages et de l'UI
 */

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
    
    // Convertir les sauts de ligne en balises <br>
    formattedMessage = formattedMessage
        .replace(/\n\n/g, '<br><br>')
        .replace(/\n/g, '<br>');
    
    messageDiv.innerHTML = `<p>${formattedMessage}</p>`;
    chatMessages.appendChild(messageDiv);
    
    // Faire défiler vers le bas pour voir le nouveau message
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    // Enregistrer le message dans l'historique
    chatHistory.push({
        role: sender === 'user' ? 'user' : 'assistant',
        content: message
    });
}

// Fonction pour afficher les sources
function displaySources(references) {
    if (!references || references.length === 0) return;
    
    const sourcesDiv = document.createElement('div');
    sourcesDiv.classList.add('message', 'bot', 'sources');
    
    let sourcesHTML = '<p><small>Sources pertinentes :</small></p>';
    
    if (references.length <= 3) {
        // Format liste pour peu de sources
        sourcesHTML += '<ul>';
        references.forEach(ref => {
            const url = ref.url || ref.source_url || "#";
            const title = ref.question || ref.title || url.replace(/^https?:\/\/[^\/]+\//, '');
            sourcesHTML += `<li><a href="${url}" target="_blank" class="source-link">${title}</a></li>`;
        });
        sourcesHTML += '</ul>';
    } else {
        // Format compact pour plusieurs sources
        sourcesHTML += '<p>';
        references.slice(0, 3).forEach((ref, index) => {
            const url = ref.url || ref.source_url || "#";
            const title = ref.question || ref.title || url.replace(/^https?:\/\/[^\/]+\//, '');
            sourcesHTML += `<a href="${url}" target="_blank" class="source-link">${title}</a>`;
            if (index < 2) sourcesHTML += ' • ';
        });
        if (references.length > 3) {
            sourcesHTML += ` et ${references.length - 3} autres sources`;
        }
        sourcesHTML += '</p>';
    }
    
    sourcesDiv.innerHTML = sourcesHTML;
    chatMessages.appendChild(sourcesDiv);
    
    // Faire défiler pour voir les sources
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Fonction pour détecter si le message concerne les formations
function isFormationRelated(message) {
    const messageLower = message.toLowerCase();
    return FORMATION_KEYWORDS.some(keyword => messageLower.includes(keyword.toLowerCase()));
}

// Fonction pour détecter si le message concerne l'orientation
function isOrientationRelated(message) {
    const messageLower = message.toLowerCase();
    return ORIENTATION_KEYWORDS.some(keyword => messageLower.includes(keyword.toLowerCase()));
}

// Fonction pour afficher les suggestions basées sur le contenu du message
function showContentBasedSuggestions(message) {
    if (isFormationRelated(message)) {
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
    
    if (isOrientationRelated(message)) {
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
}

/**
 * Fonctions pour la gestion des commandes spéciales
 */

// Fonction pour gérer les commandes spéciales
function handleSpecialCommands(message) {
    // Commande d'administration
    if (message.trim().toLowerCase() === '*admin*') {
        showAdminDialog();
        addMessageToChat("Veuillez vous authentifier pour accéder à l'interface d'administration.", 'bot');
        return true;
    }
    
    // Commande d'aide
    if (message.trim().toLowerCase() === '*aide*' || message.trim().toLowerCase() === '*help*') {
        addMessageToChat("Voici comment interagir avec moi :\n\n" +
            "- Posez-moi des questions sur les formations Bioforce, le processus de candidature, les frais, etc.\n" +
            "- Je peux vous aider à trouver des informations sur votre dossier de candidature\n" +
            "- Pour accéder à l'administration, utilisez la commande *admin*", 'bot');
        return true;
    }
    
    return false;
}

/**
 * Fonctions pour l'interaction avec l'API
 */

// Fonction pour envoyer un message à l'API
async function sendMessageToAPI(userMessage) {
    // Vérifier s'il s'agit d'une commande spéciale
    if (handleSpecialCommands(userMessage)) {
        return;
    }
    
    // Vérifier d'abord dans le cache
    const cachedResponse = findCachedResponse(userMessage);
    if (cachedResponse) {
        addMessageToChat(cachedResponse.response, 'bot');
        if (cachedResponse.references && cachedResponse.references.length > 0) {
            displaySources(cachedResponse.references);
        }
        showContentBasedSuggestions(userMessage);
        return;
    }
    
    // Ajouter indication de chargement
    const loadingDiv = document.createElement('div');
    loadingDiv.classList.add('message', 'bot', 'loading');
    loadingDiv.innerHTML = '<p>...</p>';
    chatMessages.appendChild(loadingDiv);
    
    try {
        debug("Tentative d'envoi à l'API", API_URL);
        
        // Préparation des données pour l'API
        const requestData = {
            user_id: userId,
            messages: chatHistory,
            context: {
                page: window.location.pathname,
                candidature_id: '00080932' // ID exemple pour démo
            }
        };
        
        // Appel à l'API avec timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 8000); // 8 secondes de timeout
        
        const response = await fetch(`${API_URL}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData),
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        // Supprimer l'indication de chargement
        chatMessages.removeChild(loadingDiv);
        
        if (response.ok) {
            const data = await response.json();
            debug("Réponse API reçue", data);
            
            // Afficher la réponse du chatbot
            addMessageToChat(data.message.content, 'bot');
            
            // Ajouter au cache
            addToCache(userMessage, data.message.content, data.references);
            
            // Afficher les sources si disponibles
            if (data.references && data.references.length > 0) {
                displaySources(data.references);
            }
            
            // Afficher des suggestions basées sur le contenu
            showContentBasedSuggestions(userMessage);
        } else {
            debug("Erreur API", response.status);
            
            if (CONFIG.USE_SIMULATION_FALLBACK) {
                // Utiliser la simulation en cas d'échec
                simulateAPIResponse(userMessage);
            } else {
                // Message d'erreur
                addMessageToChat("Désolé, je rencontre des difficultés à me connecter au serveur. Veuillez réessayer ou contacter l'équipe Bioforce directement.", 'bot');
            }
        }
    } catch (error) {
        debug("Erreur lors de l'appel API", error);
        
        // Supprimer l'indication de chargement si encore présente
        if (loadingDiv.parentNode === chatMessages) {
            chatMessages.removeChild(loadingDiv);
        }
        
        if (CONFIG.USE_SIMULATION_FALLBACK) {
            // Utiliser la simulation en cas d'échec
            simulateAPIResponse(userMessage);
        } else {
            // Message d'erreur
            addMessageToChat("Désolé, je rencontre des difficultés à me connecter au serveur. Veuillez réessayer ou contacter l'équipe Bioforce directement.", 'bot');
        }
    }
}

// Fonction pour simuler une réponse API (mode fallback)
function simulateAPIResponse(userMessage) {
    debug("Mode simulation activé");
    
    // Réponses prédéfinies pour la simulation
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
        "candidature": {
            content: "Pour déposer votre candidature, vous devez compléter votre dossier en ligne et régler les frais de sélection de 60€ (ou 20000 CFA pour l'Afrique). Une fois votre dossier complet, il sera examiné par notre commission d'admission.",
            source: "https://www.bioforce.org/learn/candidater/"
        },
        "financement": {
            content: "Plusieurs options de financement sont disponibles pour nos formations : bourses, prise en charge par Pôle Emploi, financement par des organismes de formation continue ou votre CPF.",
            source: "https://www.bioforce.org/learn/financer-ma-formation/"
        },
        "inscription": {
            content: "Les inscriptions se font en ligne sur notre site. Le processus comprend le dépôt d'un dossier de candidature, suivi d'un entretien de sélection pour évaluer votre motivation et votre projet professionnel.",
            source: "https://www.bioforce.org/learn/candidater/"
        },
        "frais": {
            content: "Les frais de sélection pour une candidature sont de 60€ (ou 20000 CFA pour l'Afrique). Ces frais sont à payer après avoir rempli le formulaire de candidature et avant l'évaluation de votre dossier.",
            source: "https://www.bioforce.org/learn/frais-de-selection-et-de-formation/"
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
        
        // Ajouter au cache même en mode simulation
        addToCache(userMessage, responses[bestMatch].content, [{
            url: responses[bestMatch].source,
            title: bestMatch.charAt(0).toUpperCase() + bestMatch.slice(1)
        }]);
        
        // Ajouter un lien vers la source
        if (responses[bestMatch].source) {
            displaySources([{
                url: responses[bestMatch].source,
                title: bestMatch.charAt(0).toUpperCase() + bestMatch.slice(1)
            }]);
        }
        
        // Afficher des suggestions basées sur le contenu
        showContentBasedSuggestions(userMessage);
    }, 1000);
}

/**
 * Fonctions pour l'administration
 */

// Fonction pour afficher la boîte de dialogue d'administration
function showAdminDialog() {
    if (adminOverlay && adminDialog) {
        adminOverlay.style.display = 'block';
        adminDialog.style.display = 'block';
        if (adminPassword) {
            adminPassword.value = '';
            adminPassword.focus();
        }
    } else {
        // Si les éléments n'existent pas, rediriger directement
        window.open(ADMIN_URL, '_blank');
    }
}

// Fonction pour cacher la boîte de dialogue d'administration
function hideAdminDialog() {
    if (adminOverlay && adminDialog) {
        adminOverlay.style.display = 'none';
        adminDialog.style.display = 'none';
    }
}

// Fonction pour vérifier le mot de passe admin
function checkAdminPassword() {
    const password = document.getElementById('admin-password');
    
    if (password && password.value === ADMIN_PASSWORD) {
        hideAdminDialog();
        
        // Utiliser une URL absolue sans risque de manipulation
        const cleanUrl = "https://bioforce.onrender.com/admin";
        console.log("URL avant redirection:", cleanUrl);
console.log("Document location:", window.location.href);
        // Créer un élément a et simuler un clic - approche la plus fiable
        const link = document.createElement('a');
        link.href = cleanUrl;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        
        // Message de succès
        addMessageToChat("Authentification réussie. L'interface d'administration s'ouvre dans un nouvel onglet.", 'bot');
        
        // Ajouter le lien au document, cliquer, puis le retirer
        document.body.appendChild(link);
        setTimeout(() => {
            link.click();
            document.body.removeChild(link);
        }, 100);
    } else if (password) {
        password.value = '';
        password.placeholder = 'Mot de passe incorrect';
        password.classList.add('error');
        
        setTimeout(() => {
            password.placeholder = 'Mot de passe';
            password.classList.remove('error');
        }, 2000);
    }
}

/**
 * Configuration des événements
 */

// Événement pour l'envoi de message
function handleSendMessage() {
    const message = userInput.value.trim();
    
    if (message) {
        // Ajouter le message de l'utilisateur au chat
        addMessageToChat(message, 'user');
        userInput.value = '';
        
        // Envoyer le message à l'API
        sendMessageToAPI(message);
    }
}

// Configuration des événements
sendButton.addEventListener('click', handleSendMessage);
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        handleSendMessage();
    }
});

minimizeButton.addEventListener('click', () => {
    const isMinimized = chatWidget.classList.toggle('minimized');
    minimizeButton.textContent = isMinimized ? '+' : '−';
    localStorage.setItem('chatbotMinimized', isMinimized);
});

// Configuration des événements pour l'administration
if (adminButton) {
    adminButton.addEventListener('click', showAdminDialog);
}

if (adminOverlay) {
    adminOverlay.addEventListener('click', hideAdminDialog);
}

if (cancelAdminBtn) {
    cancelAdminBtn.addEventListener('click', hideAdminDialog);
}

if (loginAdminBtn) {
    loginAdminBtn.addEventListener('click', checkAdminPassword);
}

if (adminPassword) {
    adminPassword.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            checkAdminPassword();
        }
    });
}

// Récupérer également le formulaire de contact, s'il existe
const contactForm = document.querySelector('.contact-form');

// Gestionnaire pour le formulaire de contact
if (contactForm) {
    contactForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const formData = new FormData(contactForm);
        const formDataObject = Object.fromEntries(formData.entries());
        
        try {
            const response = await fetch(`${API_URL}/contact`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(formDataObject)
            });
            
            if (response.ok) {
                alert('Votre message a été envoyé avec succès !');
                contactForm.reset();
            } else {
                alert('Une erreur est survenue lors de l\'envoi du message.');
            }
        } catch (error) {
            console.error('Erreur:', error);
            alert('Une erreur est survenue lors de l\'envoi du message.');
        }
    });
}

/**
 * Initialisation
 */

// Initialisation: Message de bienvenue si le chat est vide
window.addEventListener('DOMContentLoaded', () => {
    // Mettre le focus sur l'input
    if (userInput) {
        userInput.focus();
    }
    
    // Afficher un message de bienvenue si le chat est vide
    if (chatMessages && chatMessages.children.length === 0) {
        addMessageToChat("Bonjour ! Je suis BioforceBot, comment puis-je vous aider avec votre candidature aujourd'hui ?", 'bot');
    }
    
    debug("BioforceBot initialisé");
});