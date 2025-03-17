// Fichier: bioforcebot.js

class BioforceBot {
    constructor(options = {}) {
        this.apiUrl = options.apiUrl || 'https://api.bioforcebot.org';
        this.userId = options.userId || this._generateUserId();
        this.container = null;
        this.messages = [];
        this.context = {};
        this.isOpen = false;
        this.isLoading = false;
        
        // Messages de bienvenue selon le contexte
        this.welcomeMessages = {
            'default': "Bonjour ! Je suis BioforceBot, l'assistant virtuel de Bioforce. Comment puis-je vous aider aujourd'hui ?",
            'espace_candidat': "Bonjour ! Je suis BioforceBot, l'assistant virtuel de l'espace candidat. Je peux vous aider à naviguer dans votre espace, répondre à vos questions sur les formations ou vous assister dans votre candidature.",
            'paiement': "Bonjour ! Je vois que vous êtes en cours de candidature. Puis-je vous aider à finaliser le paiement des frais de sélection de 60€/20000 CFA ?"
        };
    }

    _generateUserId() {
        return 'user_' + Math.random().toString(36).substr(2, 9);
    }

    init(containerId, mode = 'default') {
        // Création du container
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error(`Container with id "${containerId}" not found`);
            return;
        }

        // Initialisation de l'interface
        this._createInterface();
        
        // Ajout du message de bienvenue
        const welcomeMessage = this.welcomeMessages[mode] || this.welcomeMessages.default;
        this._addMessage('assistant', welcomeMessage);

        // Événements
        this._setupEventListeners();
    }

    _createInterface() {
        // Structure principale
        this.container.innerHTML = `
            <div class="bioforcebot-wrapper">
                <div class="bioforcebot-header">
                    <div class="bioforcebot-logo">
                        <img src="https://bioforce.org/wp-content/themes/bioforce/assets/img/logo-bioforce.svg" alt="Bioforce Logo">
                    </div>
                    <div class="bioforcebot-title">BioforceBot</div>
                    <div class="bioforcebot-toggle">
                        <button class="bioforcebot-toggle-btn">
                            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">
                                <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                            </svg>
                        </button>
                    </div>
                </div>
                <div class="bioforcebot-body">
                    <div class="bioforcebot-messages"></div>
                </div>
                <div class="bioforcebot-references">
                    <div class="bioforcebot-references-header">Informations complémentaires</div>
                    <div class="bioforcebot-references-list"></div>
                </div>
                <div class="bioforcebot-footer">
                    <div class="bioforcebot-input">
                        <textarea class="bioforcebot-input-text" placeholder="Posez votre question ici..."></textarea>
                        <button class="bioforcebot-send-btn">
                            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">
                                <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
                            </svg>
                        </button>
                    </div>
                </div>
            </div>
            <button class="bioforcebot-bubble">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">
                    <path d="M20 2H4c-1.1 0-1.99.9-1.99 2L2 22l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 12H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z"/>
                </svg>
            </button>
        `;

        // Ajout des styles CSS
        const style = document.createElement('style');
        style.textContent = `
            .bioforcebot-wrapper {
                position: fixed;
                bottom: 20px;
                right: 20px;
                width: 350px;
                height: 500px;
                background: #ffffff;
                border-radius: 10px;
                box-shadow: 0 5px 20px rgba(0,0,0,0.15);
                display: flex;
                flex-direction: column;
                overflow: hidden;
                z-index: 1000;
                display: none;
                border: 1px solid #e0e0e0;
            }
            
            .bioforcebot-header {
                display: flex;
                align-items: center;
                padding: 12px 15px;
                background: #ef7d00; /* Orange Bioforce */
                color: white;
                border-bottom: 1px solid #d06c00;
            }
            
            .bioforcebot-logo {
                width: 30px;
                height: 30px;
                margin-right: 10px;
                background: white;
                border-radius: 50%;
                padding: 2px;
            }
            
            .bioforcebot-logo img {
                width: 100%;
                height: 100%;
                object-fit: contain;
            }
            
            .bioforcebot-title {
                flex-grow: 1;
                font-weight: bold;
                font-family: 'Open Sans', Arial, sans-serif;
            }
            
            .bioforcebot-toggle-btn, .bioforcebot-send-btn {
                background: none;
                border: none;
                cursor: pointer;
                color: white;
                padding: 5px;
            }
            
            .bioforcebot-toggle-btn svg, .bioforcebot-send-btn svg {
                fill: white;
            }
            
            .bioforcebot-body {
                flex-grow: 1;
                overflow-y: auto;
                padding: 15px;
                background-color: #f7f7f7; /* Fond légèrement grisé */
                background-image: url('https://bioforce.org/wp-content/themes/bioforce/assets/img/pattern-dots.png');
                background-repeat: repeat;
                background-size: 200px;
                background-blend-mode: overlay;
            }
            
            .bioforcebot-messages {
                display: flex;
                flex-direction: column;
            }
            
            .bioforcebot-message {
                margin-bottom: 10px;
                max-width: 80%;
                padding: 12px 15px;
                border-radius: 18px;
                line-height: 1.4;
                font-family: 'Open Sans', Arial, sans-serif;
                box-shadow: 0 1px 2px rgba(0,0,0,0.1);
            }
            
            .bioforcebot-message.user {
                align-self: flex-end;
                background: #eff8ff;
                border-bottom-right-radius: 4px;
                color: #2c3e50;
                border: 1px solid #d0e8ff;
            }
            
            .bioforcebot-message.assistant {
                align-self: flex-start;
                background: #ffffff;
                border-bottom-left-radius: 4px;
                color: #333333;
                border-left: 3px solid #ef7d00; /* Bordure orange Bioforce */
            }
            
            .bioforcebot-references {
                padding: 10px 15px;
                background: #f9f9f9;
                border-top: 1px solid #eee;
                max-height: 120px;
                overflow-y: auto;
                display: none;
            }
            
            .bioforcebot-references-header {
                font-weight: bold;
                margin-bottom: 5px;
                font-size: 12px;
                color: #666;
                font-family: 'Open Sans', Arial, sans-serif;
            }
            
            .bioforcebot-reference {
                margin-bottom: 8px;
                padding-bottom: 8px;
                border-bottom: 1px solid #eee;
                font-size: 12px;
                font-family: 'Open Sans', Arial, sans-serif;
            }
            
            .bioforcebot-reference-question {
                font-weight: bold;
                margin-bottom: 3px;
                color: #ef7d00; /* Orange Bioforce */
            }
            
            .bioforcebot-reference-link {
                color: #0099cc;
                text-decoration: none;
                display: block;
                margin-top: 5px;
                font-size: 11px;
            }
            
            .bioforcebot-reference-link:hover {
                text-decoration: underline;
            }
            
            .bioforcebot-footer {
                padding: 10px 15px;
                border-top: 1px solid #eee;
                background: white;
            }
            
            .bioforcebot-input {
                display: flex;
                align-items: center;
            }
            
            .bioforcebot-input-text {
                flex-grow: 1;
                border: 1px solid #ddd;
                border-radius: 20px;
                padding: 10px 15px;
                font-family: 'Open Sans', Arial, sans-serif;
                resize: none;
                height: 40px;
                outline: none;
                transition: border-color 0.2s;
            }
            
            .bioforcebot-input-text:focus {
                border-color: #ef7d00; /* Orange Bioforce */
            }
            
            .bioforcebot-send-btn {
                color: #ef7d00; /* Orange Bioforce */
                margin-left: 10px;
                width: 40px;
                height: 40px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                background: #fff;
                border: 1px solid #ef7d00;
                transition: background 0.2s;
            }
            
            .bioforcebot-send-btn:hover {
                background: #ef7d00;
            }
            
            .bioforcebot-send-btn:hover svg {
                fill: white;
            }
            
            .bioforcebot-send-btn svg {
                fill: #ef7d00;
                width: 20px;
                height: 20px;
            }
            
            .bioforcebot-bubble {
                position: fixed;
                bottom: 20px;
                right: 20px;
                width: 60px;
                height: 60px;
                border-radius: 50%;
                background: #ef7d00; /* Orange Bioforce */
                border: none;
                box-shadow: 0 5px 10px rgba(0,0,0,0.15);
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 999;
                transition: transform 0.3s, box-shadow 0.3s;
            }
            
            .bioforcebot-bubble:hover {
                transform: scale(1.05);
                box-shadow: 0 5px 15px rgba(0,0,0,0.2);
            }
            
            .bioforcebot-bubble svg {
                fill: white;
                width: 30px;
                height: 30px;
            }
            
            .bioforcebot-typing {
                display: flex;
                align-items: center;
                margin-top: 5px;
                margin-bottom: 10px;
                font-size: 12px;
                color: #888;
            }
            
            .bioforcebot-typing-indicator {
                display: flex;
                margin-left: 5px;
            }
            
            .bioforcebot-typing-dot {
                background-color: #888;
                border-radius: 50%;
                width: 5px;
                height: 5px;
                margin: 0 2px;
                animation: typing-dot 1.4s infinite ease-in-out;
            }
            
            .bioforcebot-typing-dot:nth-child(1) {
                animation-delay: 0s;
            }
            
            .bioforcebot-typing-dot:nth-child(2) {
                animation-delay: 0.2s;
            }
            
            .bioforcebot-typing-dot:nth-child(3) {
                animation-delay: 0.4s;
            }
            
            @keyframes typing-dot {
                0%, 60%, 100% {
                    transform: translateY(0);
                }
                30% {
                    transform: translateY(-5px);
                }
            }
            
            /* Média Queries pour la responsive */
            @media (max-width: 480px) {
                .bioforcebot-wrapper {
                    width: calc(100% - 40px);
                    height: calc(100% - 80px);
                    bottom: 70px;
                }
                
                .bioforcebot-bubble {
                    bottom: 10px;
                    right: 10px;
                }
            }
        `;
        
        document.head.appendChild(style);
    }

    _setupEventListeners() {
        // Bouton d'ouverture du chatbot
        const bubble = this.container.querySelector('.bioforcebot-bubble');
        bubble.addEventListener('click', () => this.open());
        
        // Bouton de fermeture du chatbot
        const toggleBtn = this.container.querySelector('.bioforcebot-toggle-btn');
        toggleBtn.addEventListener('click', () => this.close());
        
        // Envoi de message
        const sendBtn = this.container.querySelector('.bioforcebot-send-btn');
        const inputText = this.container.querySelector('.bioforcebot-input-text');
        
        const sendMessage = () => {
            const text = inputText.value.trim();
            if (text) {
                this.sendMessage(text);
                inputText.value = '';
            }
        };
        
        sendBtn.addEventListener('click', sendMessage);
        
        inputText.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }

    open() {
        const wrapper = this.container.querySelector('.bioforcebot-wrapper');
        const bubble = this.container.querySelector('.bioforcebot-bubble');
        
        wrapper.style.display = 'flex';
        bubble.style.display = 'none';
        
        this.isOpen = true;
        
        // Focus sur l'input
        const inputText = this.container.querySelector('.bioforcebot-input-text');
        inputText.focus();
    }

    close() {
        const wrapper = this.container.querySelector('.bioforcebot-wrapper');
        const bubble = this.container.querySelector('.bioforcebot-bubble');
        
        wrapper.style.display = 'none';
        bubble.style.display = 'flex';
        
        this.isOpen = false;
    }

    _addMessage(role, content) {
        const messagesContainer = this.container.querySelector('.bioforcebot-messages');
        
        // Créer élément de message
        const messageEl = document.createElement('div');
        messageEl.className = `bioforcebot-message ${role}`;
        messageEl.textContent = content;
        
        // Ajouter à la liste
        messagesContainer.appendChild(messageEl);
        
        // Scroll vers le bas
        this.container.querySelector('.bioforcebot-body').scrollTop = messagesContainer.scrollHeight;
        
        // Ajouter aux messages stockés
        this.messages.push({ role, content });
    }

    _showTypingIndicator() {
        const messagesContainer = this.container.querySelector('.bioforcebot-messages');
        
        // Créer indicateur de frappe
        const typingEl = document.createElement('div');
        typingEl.className = 'bioforcebot-typing assistant';
        typingEl.innerHTML = `
            BioforceBot est en train d'écrire
            <div class="bioforcebot-typing-indicator">
                <div class="bioforcebot-typing-dot"></div>
                <div class="bioforcebot-typing-dot"></div>
                <div class="bioforcebot-typing-dot"></div>
            </div>
        `;
        
        typingEl.id = 'bioforcebot-typing-indicator';
        
        // Ajouter à la liste
        messagesContainer.appendChild(typingEl);
        
        // Scroll vers le bas
        this.container.querySelector('.bioforcebot-body').scrollTop = messagesContainer.scrollHeight;
    }

    _removeTypingIndicator() {
        const typingIndicator = this.container.querySelector('#bioforcebot-typing-indicator');
        if (typingIndicator) {
            typingIndicator.remove();
        }
    }

    _displayReferences(references) {
        const referencesContainer = this.container.querySelector('.bioforcebot-references');
        const referencesList = this.container.querySelector('.bioforcebot-references-list');
        
        // Vider les références actuelles
        referencesList.innerHTML = '';
        
        if (references && references.length > 0) {
            // Afficher le conteneur de références
            referencesContainer.style.display = 'block';
            
            // Ajouter chaque référence
            references.forEach(ref => {
                const refEl = document.createElement('div');
                refEl.className = 'bioforcebot-reference';
                refEl.innerHTML = `
                    <div class="bioforcebot-reference-question">${ref.question}</div>
                    <a href="${ref.url}" class="bioforcebot-reference-link" target="_blank">Voir plus d'informations</a>
                `;
                referencesList.appendChild(refEl);
            });
        } else {
            // Masquer le conteneur si pas de références
            referencesContainer.style.display = 'none';
        }
    }

    async sendMessage(text) {
        if (this.isLoading) return;
        
        this.isLoading = true;
        
        // Ajouter le message utilisateur
        this._addMessage('user', text);
        
        // Afficher l'indicateur de frappe
        this._showTypingIndicator();
        
        try {
            // Préparer la requête
            const requestData = {
                user_id: this.userId,
                messages: this.messages,
                context: this.context
            };
            
            // Appeler l'API
            const response = await fetch(`${this.apiUrl}/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData)
            });
            
            if (!response.ok) {
                throw new Error('Erreur lors de la communication avec le serveur');
            }
            
            const data = await response.json();
            
            // Supprimer l'indicateur de frappe
            this._removeTypingIndicator();
            
            // Ajouter la réponse
            this._addMessage('assistant', data.message.content);
            
            // Mettre à jour le contexte
            this.context = data.context || {};
            
            // Afficher les références
            this._displayReferences(data.references);
            
        } catch (error) {
            console.error('Erreur:', error);
            
            // Supprimer l'indicateur de frappe
            this._removeTypingIndicator();
            
            // Ajouter un message d'erreur
            this._addMessage('assistant', "Désolé, j'ai rencontré un problème. Veuillez réessayer ou contacter directement l'équipe Bioforce.");
            
        } finally {
            this.isLoading = false;
        }
    }

    // Méthodes publiques pour l'intégration
    
    setContext(context) {
        this.context = {...this.context, ...context};
    }
    
    suggestQuestion(question) {
        if (!this.isOpen) {
            this.open();
        }
        
        const inputText = this.container.querySelector('.bioforcebot-input-text');
        inputText.value = question;
        inputText.focus();
    }
}

// Exportation pour utilisation dans d'autres fichiers
if (typeof module !== 'undefined' && typeof module.exports !== 'undefined') {
    module.exports = BioforceBot;
} else {
    window.BioforceBot = BioforceBot;
}