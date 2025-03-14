// Configuration de l'API
// Possibilité de choisir entre l'API locale et l'API en production
const API_LOCAL = 'http://localhost:8000'; 
const API_PRODUCTION = 'https://bioforce.onrender.com';  // URL exacte de votre API sur Render
const USE_PRODUCTION_API = window.location.hostname.includes('render.com'); // Détection automatique
const API_URL = USE_PRODUCTION_API ? API_PRODUCTION : API_LOCAL;
const USE_SIMULATION_FALLBACK = true; // Mode simulation toujours activé comme plan B

// Éléments DOM
const chatWidget = document.getElementById('chatbot-widget');
const chatHeader = chatWidget.querySelector('.chat-header');
const chatMessages = document.getElementById('chat-messages');
const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-message');
const minimizeButton = document.getElementById('minimize-chat');

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
    // Ne pas déclencher le déplacement si on touche le bouton de minimisation
    if (e.target === minimizeButton || e.target.closest('#minimize-chat')) {
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

// Fonction pour envoyer un message à l'API
async function sendMessageToAPI(userMessage) {
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
            
            // Afficher les références si disponibles
            if (apiResponse.references && apiResponse.references.length > 0) {
                const referencesDiv = document.createElement('div');
                referencesDiv.classList.add('message', 'bot', 'references');
                
                let referencesContent = '<p><small><em>Sources:</em><br>';
                apiResponse.references.forEach((ref, index) => {
                    referencesContent += `${index + 1}. ${ref.question}<br>`;
                });
                referencesContent += '</small></p>';
                
                referencesDiv.innerHTML = referencesContent;
                chatMessages.appendChild(referencesDiv);
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

// Mode de démonstration - simulation des réponses sans API
function simulateAPIResponse(userMessage) {
    setTimeout(() => {
        let botResponse;
        
        // Quelques réponses prédéfinies pour la démonstration
        if (userMessage.toLowerCase().includes('formation')) {
            botResponse = "Les formations Bioforce vous préparent aux métiers de l'humanitaire. Nous proposons plusieurs parcours selon vos objectifs. Avez-vous une idée du domaine qui vous intéresse : logistique, management, RH, finances ?";
        } 
        else if (userMessage.toLowerCase().includes('frais') || userMessage.toLowerCase().includes('payer') || userMessage.toLowerCase().includes('coût')) {
            botResponse = "Les frais de candidature s'élèvent à 60€/20000 CFA. C'est une étape nécessaire pour accéder à la sélection. Le paiement peut être effectué en ligne. Avez-vous des difficultés à finaliser cette étape ?";
        }
        else if (userMessage.toLowerCase().includes('candidature') || userMessage.toLowerCase().includes('dossier')) {
            botResponse = "Pour compléter votre dossier de candidature, vous devez fournir plusieurs documents : CV, lettre de motivation, copie de pièce d'identité et justificatifs de diplômes. Vous pouvez les télécharger dans la section 'Documents à fournir' de votre espace candidat.";
        }
        else if (userMessage.toLowerCase().includes('sélection') || userMessage.toLowerCase().includes('entretien')) {
            botResponse = "Le processus de sélection comprend plusieurs étapes : l'analyse de votre dossier, un test écrit et un entretien individuel. Une fois votre dossier complet et les frais de candidature réglés, vous serez convoqué aux épreuves de sélection.";
        }
        else if (userMessage.toLowerCase().includes('contact') || userMessage.toLowerCase().includes('aide')) {
            botResponse = "Pour toute question, vous pouvez contacter notre équipe par email à infoeurope@bioforce.org ou par téléphone au +33 (0)4 37 41 30 30. Nos bureaux sont ouverts du lundi au vendredi de 9h à 17h.";
        }
        else {
            botResponse = "Merci pour votre message. En tant qu'assistant de Bioforce, je suis là pour vous aider dans votre processus de candidature. Avez-vous des questions spécifiques sur nos formations, le processus de sélection ou les documents à fournir ?";
        }
        
        // Ajouter la réponse simulée au chat
        addMessageToChat(botResponse, 'bot');
        
    }, 1000); // Délai simulé pour donner l'impression d'un traitement
}

// Event Listeners
sendButton.addEventListener('click', () => {
    const message = userInput.value.trim();
    
    if (message) {
        // Ajouter le message de l'utilisateur à l'interface
        addMessageToChat(message, 'user');
        
        // Vider l'input
        userInput.value = '';
        
        // Utiliser l'API réelle au lieu de la simulation
        sendMessageToAPI(message);
    }
});

userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendButton.click();
    }
});

minimizeButton.addEventListener('click', () => {
    const chatbotBody = document.querySelector('.chatbot-body');
    
    if (chatbotBody.style.display === 'none') {
        chatbotBody.style.display = 'flex';
        minimizeButton.textContent = '−';
    } else {
        chatbotBody.style.display = 'none';
        minimizeButton.textContent = '+';
    }
});

// Initialisation
document.addEventListener('DOMContentLoaded', () => {
    // Message de bienvenue initial déjà dans le HTML
    
    // Mettre le focus sur l'input
    userInput.focus();
});
