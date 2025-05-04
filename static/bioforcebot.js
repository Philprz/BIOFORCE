// Définition de l'URL d'administration (sans slash final)
const API_URL = window.location.origin;
const ADMIN_PATH = 'admin'; // Sans slash au début ni à la fin
const ADMIN_URL = normalizeUrl(API_URL, ADMIN_PATH);

// Configuration de l'administration
const ADMIN_PASSWORD = "bioforce2025"; 
// Fonction utilitaire pour normaliser les URLs et éviter les doubles slashes
function normalizeUrl(baseUrl, path) {
    // Si baseUrl se termine par un slash et que path commence par un slash,
    // on supprime le slash au début du path
    if (baseUrl.endsWith('/') && path.startsWith('/')) {
        path = path.substring(1);
    } 
    // Si baseUrl ne se termine pas par un slash et que path ne commence pas par un slash,
    // on ajoute un slash entre les deux
    else if (!baseUrl.endsWith('/') && !path.startsWith('/')) {
        path = '/' + path;
    }
    return baseUrl + path;
}
// Éléments DOM
const chatWidget = document.getElementById('chatbot-widget');
const chatHeader = chatWidget.querySelector('.chat-header');
const chatMessages = document.getElementById('chat-messages');
const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-message');
const minimizeButton = document.getElementById('minimize-chat');
const adminButton = document.querySelector('#admin-btn');

// Récupérer également le formulaire de contact, s'il existe
const contactForm = document.querySelector('.contact-form');

// Variables globales
let isDragging = false;
let dragOffsetX, dragOffsetY;
let chatHistory = [];
let userId = 'user-' + Math.floor(Math.random() * 1000);

// Récupérer la position du chatbot stockée dans localStorage
const savedPosition = JSON.parse(localStorage.getItem('chatbotPosition'));
if (savedPosition) {
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
    if (e.target === minimizeButton || e.target === adminButton || 
        e.target.closest('#minimize-chat') || e.target.closest('#admin-btn')) {
        return;
    }

    isDragging = true;
    chatWidget.classList.add('dragging');
    
    const rect = chatWidget.getBoundingClientRect();
    
    if (e.type === 'mousedown') {
        dragOffsetX = e.clientX - rect.left;
        dragOffsetY = e.clientY - rect.top;
    } else if (e.type === 'touchstart') {
        dragOffsetX = e.touches[0].clientX - rect.left;
        dragOffsetY = e.touches[0].clientY - rect.top;
    }
    
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
        e.preventDefault();
    }
    
    let left = clientX - dragOffsetX;
    let top = clientY - dragOffsetY;
    
    const maxX = window.innerWidth - chatWidget.offsetWidth;
    const maxY = window.innerHeight - chatWidget.offsetHeight;
    
    left = Math.max(0, Math.min(maxX, left));
    top = Math.max(0, Math.min(maxY, top));
    
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
        
        const position = {
            left: parseInt(chatWidget.style.left),
            top: parseInt(chatWidget.style.top)
        };
        localStorage.setItem('chatbotPosition', JSON.stringify(position));
    }
}

// Gestionnaires d'événements tactiles
function handleTouchStart(e) {
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

// Fonction pour ajouter un message au chat
function addMessageToChat(message, sender) {
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', sender);
    
    let formattedMessage = message;
    
    // Gérer les listes (puces avec astérisques)
    if (message.includes('**')) {
        formattedMessage = formattedMessage
            .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
            .replace(/\n\*\*([^*]+)\*\*/g, '<br><br><strong>$1</strong>');
            
        if (formattedMessage.includes('<br><strong>')) {
            const parts = formattedMessage.split('<br><br>');
            const intro = parts.shift();
            
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
    
    formattedMessage = formattedMessage
        .replace(/\n\n/g, '<br><br>')
        .replace(/\n/g, '<br>');
    
    messageDiv.innerHTML = `<p>${formattedMessage}</p>`;
    chatMessages.appendChild(messageDiv);
    
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    chatHistory.push({
        role: sender === 'user' ? 'user' : 'assistant',
        content: message
    });
}

// Fonction pour afficher les sources
function displaySources(references) {
    if (!references || references.length === 0) return;
    
    // Supprimer les anciennes sources s'il y en a
    const oldSources = document.querySelector('.message.bot.sources');
    if (oldSources) {
        oldSources.remove();
    }
    
    // Créer un élément pour afficher les sources
    const sourcesDiv = document.createElement('div');
    sourcesDiv.classList.add('message', 'bot', 'sources');
    
    let sourcesHTML = '<p><small>Sources pertinentes :</small></p><ul>';
    
    // Ajouter chaque source comme un lien
    references.forEach(ref => {
        const url = ref.url || ref.source || "#";
        const title = ref.question || ref.title || "Source";
        
        sourcesHTML += `<li><a href="${url}" target="_blank" class="source-link">${title}</a></li>`;
    });
    
    sourcesHTML += '</ul>';
    sourcesDiv.innerHTML = sourcesHTML;
    chatMessages.appendChild(sourcesDiv);
    
    // Faire défiler pour voir les sources
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Fonction pour envoyer un message à l'API
async function sendMessageToAPI(userMessage) {
    // Ajouter indication de chargement
    const loadingDiv = document.createElement('div');
    loadingDiv.classList.add('message', 'bot', 'loading');
    loadingDiv.innerHTML = '<p>...</p>';
    chatMessages.appendChild(loadingDiv);
    
    try {
        // Préparation des données pour l'API
        const requestData = {
            user_id: userId,
            messages: chatHistory,
            context: {
                page: window.location.pathname,
                candidature_id: '00080932'  // ID exemple pour démo
            }
        };
        
        // Appel à l'API
        const response = await fetch(`${API_URL}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });
        
        // Supprimer l'indication de chargement
        chatMessages.removeChild(loadingDiv);
        
        if (response.ok) {
            const data = await response.json();
            
            // Afficher la réponse du chatbot
            addMessageToChat(data.message.content, 'bot');
            
            // Afficher les sources si disponibles
            if (data.references && data.references.length > 0) {
                displaySources(data.references);
            }
        } else {
            // Gestion des erreurs
            console.error('Erreur API:', await response.text());
            addMessageToChat("Désolé, je rencontre des difficultés techniques. Veuillez réessayer ou contacter l'équipe Bioforce directement.", 'bot');
        }
    } catch (error) {
        console.error('Erreur:', error);
        
        // Supprimer l'indication de chargement en cas d'erreur
        if (loadingDiv.parentNode) {
            chatMessages.removeChild(loadingDiv);
        }
        
        // Message d'erreur
        addMessageToChat("Désolé, je rencontre des difficultés techniques. Veuillez réessayer ou contacter l'équipe Bioforce directement.", 'bot');
    }
}

// Fonction pour gérer l'envoi du message
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

// Fonctions pour l'administration
function showAdminDialog() {
    const adminOverlay = document.getElementById('admin-overlay');
    const adminDialog = document.getElementById('admin-dialog');
    
    if (adminOverlay && adminDialog) {
        adminOverlay.style.display = 'block';
        adminDialog.style.display = 'block';
        document.getElementById('admin-password').value = '';
        document.getElementById('admin-password').focus();
    } else {
        window.open(ADMIN_URL, '_blank');
    }
}

function hideAdminDialog() {
    const adminOverlay = document.getElementById('admin-overlay');
    const adminDialog = document.getElementById('admin-dialog');
    
    if (adminOverlay && adminDialog) {
        adminOverlay.style.display = 'none';
        adminDialog.style.display = 'none';
    }
}

function checkAdminPassword() {
    const adminPassword = document.getElementById('admin-password');
    
    if (adminPassword && adminPassword.value === ADMIN_PASSWORD) {
        hideAdminDialog();
        
        // Utiliser l'URL en dur
        window.open(ADMIN_URL, '_blank');
        
        addMessageToChat("Authentification réussie. L'interface d'administration s'ouvre dans un nouvel onglet.", 'bot');
    } else if (adminPassword) {
        adminPassword.value = '';
        adminPassword.placeholder = 'Mot de passe incorrect';
        adminPassword.classList.add('error');
        
        setTimeout(() => {
            adminPassword.placeholder = 'Mot de passe';
            adminPassword.classList.remove('error');
        }, 2000);
    }
}

// Gestionnaires d'événements
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

// Gestionnaires pour l'administration
if (adminButton) {
    adminButton.addEventListener('click', showAdminDialog);
    
    // Chercher les éléments de la boîte de dialogue
    const cancelAdminBtn = document.getElementById('cancel-admin');
    const loginAdminBtn = document.getElementById('login-admin');
    const adminOverlay = document.getElementById('admin-overlay');
    
    if (cancelAdminBtn) cancelAdminBtn.addEventListener('click', hideAdminDialog);
    if (loginAdminBtn) loginAdminBtn.addEventListener('click', checkAdminPassword);
    if (adminOverlay) adminOverlay.addEventListener('click', hideAdminDialog);
    
    // Écouter la touche Entrée dans le champ de mot de passe
    const adminPassword = document.getElementById('admin-password');
    if (adminPassword) {
        adminPassword.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                checkAdminPassword();
            }
        });
    }
}

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

// Restaurer l'état minimisé du chatbot
if (localStorage.getItem('chatbotMinimized') === 'true') {
    chatWidget.classList.add('minimized');
    minimizeButton.textContent = '+';
}

// Initialisation: Message de bienvenue si le chat est vide
window.addEventListener('DOMContentLoaded', () => {
    if (chatMessages.children.length === 0) {
        addMessageToChat("Bonjour ! Je suis BioforceBot, comment puis-je vous aider avec votre candidature aujourd'hui ?", 'bot');
    }
});