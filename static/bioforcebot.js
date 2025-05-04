class BioforceBot {
    constructor(options = {}) {
        this.apiUrl = options.apiUrl || 'http://localhost:8000';
        this.userId = options.userId || this._generateUserId();
        this.container = null;
        this.messages = [];
        this.context = {};
        this.isOpen = false;
        this.isLoading = false;
        this.welcomeMessages = {
            'default': "Bonjour ! Je suis BioforceBot, l'assistant virtuel de Bioforce. Comment puis-je vous aider aujourd'hui ?",
            'espace_candidat': "Bonjour ! Je suis BioforceBot, l'assistant virtuel de l'espace candidat. Je peux vous aider à naviguer dans votre espace, répondre à vos questions sur les formations ou vous assister dans votre candidature."
        };
    }

    _generateUserId() {
        return 'user_' + Math.random().toString(36).substr(2, 9);
    }

    init(containerId, mode = 'default') {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error(`Container with id "${containerId}" not found`);
            return;
        }

        this._createInterface();
        const welcomeMessage = this.welcomeMessages[mode] || this.welcomeMessages.default;
        this._addMessage('assistant', welcomeMessage);
        this._setupEventListeners();
        
        console.log("BioforceBot initialized with API URL:", this.apiUrl);
    }

    _createInterface() {
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
                background: #ef7d00;
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
                background-color: #f7f7f7;
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
                position: relative;
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
                border-left: 3px solid #ef7d00;
            }

            .bioforcebot-message.enrichment {
                align-self: flex-start;
                background: #f0f7ff;
                border-bottom-left-radius: 4px;
                color: #333333;
                border-left: 3px solid #2196F3;
                margin-top: -5px;
            }

            .bioforcebot-typing {
                align-self: flex-start;
                background: #f5f5f5;
                padding: 10px 15px;
                border-radius: 18px;
                display: flex;
                align-items: center;
                margin-bottom: 10px;
            }

            .bioforcebot-typing-dots {
                display: flex;
                align-items: center;
            }

            .bioforcebot-typing-dot {
                width: 8px;
                height: 8px;
                background-color: #999;
                border-radius: 50%;
                margin: 0 2px;
                animation: typing 1.4s infinite ease-in-out;
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

            @keyframes typing {
                0%, 60%, 100% {
                    transform: translateY(0);
                }
                30% {
                    transform: translateY(-5px);
                }
            }

            .bioforcebot-references {
                padding: 10px 15px;
                background: #f9f9f9;
                border-top: 1px solid #eee;
                max-height: 120px;
                overflow-y: auto;
                display: block;
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
                color: #ef7d00;
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
                border-color: #ef7d00;
            }

            .bioforcebot-send-btn {
                color: #ef7d00;
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
                background: #ef7d00;
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

            @media (max-width: 480px) {
                .bioforcebot-wrapper {
                    width: 100%;
                    bottom: 0;
                    right: 0;
                    border-radius: 0;
                    height: 100vh;
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
        const bubble = this.container.querySelector('.bioforcebot-bubble');
        bubble.addEventListener('click', () => this.open());

        const toggleBtn = this.container.querySelector('.bioforcebot-toggle-btn');
        toggleBtn.addEventListener('click', () => this.close());

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

        const inputText = this.container.querySelector('.bioforcebot-input-text');
        inputText.focus();
    }

    close() {
        const wrapper = this.container.querySelector('.bioforcebot-wrapper');
        const bubble = this.container.querySelector('.bioforcebot-bubble');

        wrapper.style.display = 'none';
        bubble.style.display = 'flex';

        this.isOpen = false;

        this._closeWebSocketConnection();
    }

    _addMessage(role, content, messageType = 'default') {
        const messagesContainer = this.container.querySelector('.bioforcebot-messages');

        const messageEl = document.createElement('div');
        messageEl.className = `bioforcebot-message ${role}`;

        if (messageType !== 'default') {
            messageEl.classList.add(messageType);
        }

        if (role === 'assistant' && content.includes('<a href=')) {
            messageEl.innerHTML = content;
        } else {
            let formattedContent = this._formatMessage(content);
            messageEl.innerHTML = formattedContent;
        }

        messagesContainer.appendChild(messageEl);
        this._scrollToBottom();

        if (role === 'user' || (role === 'assistant' && messageType === 'default')) {
            if (role === 'assistant' && content.includes('<a href=')) {
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = content;
                this.messages.push({ role, content: tempDiv.textContent });
            } else {
                this.messages.push({ role, content });
            }
        }
    }

    _formatMessage(content) {
        let formatted = content;
        formatted = formatted.replace(/\n/g, '<br>');
        formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        formatted = formatted.replace(/\*(.*?)\*/g, '<em>$1</em>');
        return formatted;
    }

    _scrollToBottom() {
        const messagesContainer = this.container.querySelector('.bioforcebot-messages');
        const body = this.container.querySelector('.bioforcebot-body');
        body.scrollTop = messagesContainer.scrollHeight;
    }

    _showTypingIndicator() {
        const messagesContainer = this.container.querySelector('.bioforcebot-messages');

        const typingEl = document.createElement('div');
        typingEl.className = 'bioforcebot-typing';
        typingEl.id = 'bioforcebot-typing';

        typingEl.innerHTML = `
            <div class="bioforcebot-typing-dots">
                <div class="bioforcebot-typing-dot"></div>
                <div class="bioforcebot-typing-dot"></div>
                <div class="bioforcebot-typing-dot"></div>
            </div>
        `;

        messagesContainer.appendChild(typingEl);
        this._scrollToBottom();
    }

    _removeTypingIndicator() {
        const typingIndicator = this.container.querySelector('#bioforcebot-typing');
        if (typingIndicator) {
            typingIndicator.remove();
        }
    }

    _displayReferences(references) {
        const referencesContainer = this.container.querySelector('.bioforcebot-references');
        const referencesList = this.container.querySelector('.bioforcebot-references-list');
    
        referencesList.innerHTML = '';
        
        console.log("References received:", references); // Ajoutez ce log pour déboguer
        
        if (references && references.length > 0) {
            referencesContainer.style.display = 'block';
    
            references.forEach(ref => {
                const refEl = document.createElement('div');
                refEl.className = 'bioforcebot-reference';
    
                // Vérification des propriétés pour éviter les erreurs
                const titleText = ref.title || ref.question || "Information";
                const sourceUrl = ref.source || "#";
    
                refEl.innerHTML = `
                    <div class="bioforcebot-reference-question">${titleText}</div>
                    <a href="${sourceUrl}" class="bioforcebot-reference-link" target="_blank">
                        ${sourceUrl.includes('bioforce.org') ? sourceUrl.replace('https://bioforce.org/', '') : 'Source externe'}
                    </a>
                `;
    
                referencesList.appendChild(refEl);
            });
        } else {
            referencesContainer.style.display = 'none';
        }
    }

    _setupWebSocketConnection(websocketId) {
        this._closeWebSocketConnection();

        this.websocketId = websocketId;

        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsBase = this.apiUrl.replace(/^https?:/, wsProtocol);
        const wsUrl = `${wsBase}/ws/${websocketId}`;
        console.log(`Tentative de connexion WebSocket à ${wsUrl}`);
        try {
            this.websocket = new WebSocket(wsUrl);

            this.websocket.onopen = () => {
                console.log('WebSocket connection established');
                this._addMessage(
                    'assistant',
                    "Je recherche actuellement des informations complémentaires en ligne pour enrichir ma réponse...",
                    'notification'
                );
            };

            this.websocket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);

                    if (data.type === 'enrichment') {
                        this._addMessage('assistant', data.content, 'enrichment');
                        this._scrollToBottom();
                    } else if (data.type === 'no_enrichment') {
                        this._addMessage(
                            'assistant',
                            "J'ai vérifié les informations les plus récentes et je confirme que ma réponse précédente est à jour.",
                            'notification'
                        );
                    } else if (data.type === 'error') {
                        console.error('Enrichment error:', data.content);
                    }
                } catch (e) {
                    console.error('Error parsing WebSocket message:', e);
                }
            };

            this.websocket.onerror = (error) => {
                console.error('WebSocket error:', error);
            };

            this.websocket.onclose = () => {
                console.log('WebSocket connection closed');
                this.websocket = null;
            };

        } catch (e) {
            console.error('Error setting up WebSocket:', e);
        }
    }

    _closeWebSocketConnection() {
        if (this.websocket) {
            this.websocket.close();
            this.websocket = null;
        }
    }

    async sendMessage(text) {
        if (this.isLoading) return;
    
        this.isLoading = true;
        this._addMessage('user', text);
        this._showTypingIndicator();
    
        try {
            console.log("Sending message to API:", text);
            
            const requestData = {
                user_id: this.userId,
                messages: this.messages.slice(-2), // ne garde que les 2 derniers messages
                context: this.context
            };
            console.log("PAYLOAD:", JSON.stringify(requestData));
            const response = await fetch(`${this.apiUrl}/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData)
            });
    
            this._removeTypingIndicator();
    
            if (!response.ok) {
                throw new Error(`HTTP error ${response.status}`);
            }
    
            const data = await response.json();
            console.log("Response received:", data); // Pour vérifier le format de la réponse
    
            this._addMessage('assistant', data.message.content);
            this.context = data.context || {};
            
            // S'assurer que les références sont bien passées à la fonction d'affichage
            if (data.references && Array.isArray(data.references)) {
                this._displayReferences(data.references);
            } else {
                this._displayReferences([]);
            }
    
        } catch (error) {
            console.error('Error:', error);
            this._removeTypingIndicator();
            this._addMessage('assistant', "Désolé, j'ai rencontré un problème technique. Veuillez réessayer ou contacter directement l'équipe Bioforce.");
        } finally {
            this.isLoading = false;
        }
    }
}

// Export pour utilisation dans le navigateur
if (typeof window !== 'undefined') {
    window.BioforceBot = BioforceBot;
}