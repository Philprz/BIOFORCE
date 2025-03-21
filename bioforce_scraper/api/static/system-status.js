/**
 * Script pour intégrer l'indicateur d'état système (feu tricolore)
 * à insérer dans les pages du chatbot
 */

class SystemStatusIndicator {
    constructor(options = {}) {
        this.options = Object.assign({
            apiUrl: '/system-status',
            containerId: 'system-status-container',
            position: 'top-right',      // 'top-right', 'top-left', 'bottom-right', 'bottom-left'
            size: 'small',              // 'small', 'medium', 'large'
            showDetails: true,          // afficher les détails au clic
            autoRefresh: true,          // rafraîchir automatiquement
            refreshInterval: 60000,     // intervalle de rafraîchissement en ms (1 minute)
            theme: 'light'              // 'light' ou 'dark'
        }, options);
        
        this.container = null;
        this.statusData = null;
        this.initialized = false;
        this.statusColors = {
            green: '#2ecc71',  // Vert
            orange: '#f39c12', // Orange
            red: '#e74c3c',    // Rouge
            unknown: '#95a5a6' // Gris
        };
        
        this.refreshTimer = null;
    }
    
    /**
     * Initialise l'indicateur et l'ajoute au DOM
     */
    init() {
        // Créer l'élément conteneur s'il n'existe pas déjà
        this.container = document.getElementById(this.options.containerId);
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.id = this.options.containerId;
            document.body.appendChild(this.container);
        }
        
        // Appliquer les styles de base au conteneur
        this.container.className = `system-status-container ${this.options.position} ${this.options.size} ${this.options.theme}`;
        
        // Ajouter les styles CSS
        this._addStyles();
        
        // Créer la structure de l'indicateur
        this.container.innerHTML = `
            <div class="status-indicator" title="État du système">
                <div class="status-light unknown"></div>
            </div>
            <div class="status-details">
                <div class="status-details-header">
                    <h3>État du système</h3>
                    <span class="close-details">&times;</span>
                </div>
                <div class="status-details-content">
                    <div class="service-details">
                        <p>Chargement de l'état du système...</p>
                    </div>
                </div>
                <div class="status-details-footer">
                    <span class="status-timestamp">-</span>
                </div>
            </div>
        `;
        
        // Ajouter les gestionnaires d'événements
        this._addEventListeners();
        
        // Récupérer l'état initial
        this.refresh();
        
        // Configurer le rafraîchissement automatique
        if (this.options.autoRefresh) {
            this.refreshTimer = setInterval(() => {
                this.refresh();
            }, this.options.refreshInterval);
        }
        
        this.initialized = true;
        return this;
    }
    
    /**
     * Rafraîchit l'état du système
     */
    async refresh() {
        try {
            const response = await fetch(this.options.apiUrl);
            if (!response.ok) {
                throw new Error(`Erreur HTTP: ${response.status}`);
            }
            
            this.statusData = await response.json();
            this._updateIndicator();
        } catch (error) {
            console.error('Erreur lors de la récupération de l\'état du système:', error);
            this._setErrorState(error.message);
        }
    }
    
    /**
     * Met à jour l'indicateur avec les données actuelles
     */
    _updateIndicator() {
        if (!this.statusData) return;
        
        const statusLight = this.container.querySelector('.status-light');
        const overallStatus = this.statusData.overall_status;
        
        // Enlever toutes les classes de statut
        statusLight.classList.remove('green', 'orange', 'red', 'unknown');
        
        // Ajouter la classe correspondant au statut actuel
        statusLight.classList.add(overallStatus);
        
        // Mettre à jour le contenu des détails
        if (this.options.showDetails) {
            const detailsContent = this.container.querySelector('.service-details');
            const timestamp = this.container.querySelector('.status-timestamp');
            
            // Formater les détails des services
            let servicesHtml = '';
            for (const [name, service] of Object.entries(this.statusData.services)) {
                servicesHtml += `
                    <div class="service-item">
                        <div class="service-name">${service.name}</div>
                        <div class="service-status ${service.status}">
                            <span class="status-dot"></span>
                            ${service.status.toUpperCase()}
                        </div>
                        <div class="service-message">${service.message}</div>
                    </div>
                `;
            }
            
            detailsContent.innerHTML = servicesHtml;
            timestamp.textContent = `Dernière vérification: ${new Date().toLocaleString()}`;
        }
    }
    
    /**
     * Définit l'état d'erreur
     */
    _setErrorState(message) {
        const statusLight = this.container.querySelector('.status-light');
        statusLight.classList.remove('green', 'orange', 'red', 'unknown');
        statusLight.classList.add('red');
        
        if (this.options.showDetails) {
            const detailsContent = this.container.querySelector('.service-details');
            detailsContent.innerHTML = `
                <div class="error-message">
                    <p>Impossible de récupérer l'état du système</p>
                    <small>${message}</small>
                </div>
            `;
        }
    }
    
    /**
     * Ajoute les gestionnaires d'événements
     */
    _addEventListeners() {
        // Gestionnaire pour afficher/masquer les détails
        const indicator = this.container.querySelector('.status-indicator');
        const details = this.container.querySelector('.status-details');
        const closeBtn = this.container.querySelector('.close-details');
        
        indicator.addEventListener('click', () => {
            details.classList.toggle('visible');
        });
        
        closeBtn.addEventListener('click', () => {
            details.classList.remove('visible');
        });
    }
    
    /**
     * Ajoute les styles CSS
     */
    _addStyles() {
        // Vérifier si les styles existent déjà
        if (document.getElementById('system-status-styles')) return;
        
        const styleEl = document.createElement('style');
        styleEl.id = 'system-status-styles';
        
        styleEl.textContent = `
            /* Styles pour l'indicateur d'état du système */
            .system-status-container {
                position: fixed;
                z-index: 9999;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }
            
            /* Positions */
            .system-status-container.top-right {
                top: 20px;
                right: 20px;
            }
            .system-status-container.top-left {
                top: 20px;
                left: 20px;
            }
            .system-status-container.bottom-right {
                bottom: 20px;
                right: 20px;
            }
            .system-status-container.bottom-left {
                bottom: 20px;
                left: 20px;
            }
            
            /* Tailles */
            .system-status-container.small .status-indicator {
                width: 24px;
                height: 24px;
            }
            .system-status-container.medium .status-indicator {
                width: 32px;
                height: 32px;
            }
            .system-status-container.large .status-indicator {
                width: 40px;
                height: 40px;
            }
            
            /* Indicateur */
            .status-indicator {
                border-radius: 50%;
                background-color: #fff;
                box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
                display: flex;
                align-items: center;
                justify-content: center;
                cursor: pointer;
                transition: transform 0.2s ease;
            }
            
            .status-indicator:hover {
                transform: scale(1.1);
            }
            
            .status-light {
                width: 60%;
                height: 60%;
                border-radius: 50%;
                transition: background-color 0.3s ease;
            }
            
            .status-light.green {
                background-color: #2ecc71;
                box-shadow: 0 0 10px #2ecc71;
            }
            .status-light.orange {
                background-color: #f39c12;
                box-shadow: 0 0 10px #f39c12;
            }
            .status-light.red {
                background-color: #e74c3c;
                box-shadow: 0 0 10px #e74c3c;
            }
            .status-light.unknown {
                background-color: #95a5a6;
                box-shadow: 0 0 10px #95a5a6;
            }
            
            /* Détails */
            .status-details {
                display: none;
                position: absolute;
                width: 300px;
                background-color: white;
                border-radius: 8px;
                box-shadow: 0 3px 15px rgba(0, 0, 0, 0.2);
                margin-top: 10px;
                overflow: hidden;
                transition: all 0.3s ease;
                max-height: 400px;
                overflow-y: auto;
            }
            
            .system-status-container.top-right .status-details,
            .system-status-container.bottom-right .status-details {
                right: 0;
            }
            
            .system-status-container.top-left .status-details,
            .system-status-container.bottom-left .status-details {
                left: 0;
            }
            
            .status-details.visible {
                display: block;
                animation: fadeIn 0.3s ease;
            }
            
            .status-details-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 12px 15px;
                border-bottom: 1px solid #eee;
                background-color: #f9f9f9;
            }
            
            .status-details-header h3 {
                margin: 0;
                font-size: 16px;
                color: #333;
            }
            
            .close-details {
                font-size: 20px;
                color: #999;
                cursor: pointer;
                transition: color 0.2s ease;
            }
            
            .close-details:hover {
                color: #333;
            }
            
            .status-details-content {
                padding: 15px;
            }
            
            .service-item {
                margin-bottom: 15px;
                padding-bottom: 15px;
                border-bottom: 1px solid #f5f5f5;
            }
            
            .service-item:last-child {
                margin-bottom: 0;
                padding-bottom: 0;
                border-bottom: none;
            }
            
            .service-name {
                font-weight: bold;
                margin-bottom: 5px;
                color: #333;
            }
            
            .service-status {
                display: flex;
                align-items: center;
                font-size: 12px;
                font-weight: bold;
                margin-bottom: 5px;
            }
            
            .service-status .status-dot {
                width: 8px;
                height: 8px;
                border-radius: 50%;
                margin-right: 5px;
            }
            
            .service-status.green {
                color: #2ecc71;
            }
            .service-status.green .status-dot {
                background-color: #2ecc71;
            }
            
            .service-status.orange {
                color: #f39c12;
            }
            .service-status.orange .status-dot {
                background-color: #f39c12;
            }
            
            .service-status.red {
                color: #e74c3c;
            }
            .service-status.red .status-dot {
                background-color: #e74c3c;
            }
            
            .service-status.unknown {
                color: #95a5a6;
            }
            .service-status.unknown .status-dot {
                background-color: #95a5a6;
            }
            
            .service-message {
                font-size: 13px;
                color: #666;
                line-height: 1.4;
            }
            
            .error-message {
                color: #e74c3c;
                text-align: center;
                padding: 10px;
            }
            
            .error-message p {
                margin: 0 0 10px 0;
                font-weight: bold;
            }
            
            .error-message small {
                font-size: 12px;
                color: #666;
            }
            
            .status-details-footer {
                padding: 10px 15px;
                background-color: #f9f9f9;
                border-top: 1px solid #eee;
                text-align: center;
                font-size: 12px;
                color: #999;
            }
            
            /* Thème sombre */
            .system-status-container.dark .status-indicator {
                background-color: #333;
            }
            
            .system-status-container.dark .status-details {
                background-color: #333;
                color: #eee;
            }
            
            .system-status-container.dark .status-details-header {
                background-color: #222;
                border-bottom-color: #444;
            }
            
            .system-status-container.dark .status-details-header h3 {
                color: #eee;
            }
            
            .system-status-container.dark .close-details {
                color: #ccc;
            }
            
            .system-status-container.dark .close-details:hover {
                color: #fff;
            }
            
            .system-status-container.dark .service-item {
                border-bottom-color: #444;
            }
            
            .system-status-container.dark .service-name {
                color: #eee;
            }
            
            .system-status-container.dark .service-message {
                color: #ccc;
            }
            
            .system-status-container.dark .status-details-footer {
                background-color: #222;
                border-top-color: #444;
                color: #ccc;
            }
            
            /* Animations */
            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(-10px); }
                to { opacity: 1; transform: translateY(0); }
            }
        `;
        
        document.head.appendChild(styleEl);
    }
    
    /**
     * Nettoie l'instance
     */
    destroy() {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
        }
        
        if (this.container) {
            document.body.removeChild(this.container);
        }
        
        const styleEl = document.getElementById('system-status-styles');
        if (styleEl) {
            document.head.removeChild(styleEl);
        }
    }
}

// Fonction d'initialisation automatique
function initSystemStatusIndicator(options = {}) {
    document.addEventListener('DOMContentLoaded', () => {
        window.systemStatusIndicator = new SystemStatusIndicator(options).init();
    });
}
