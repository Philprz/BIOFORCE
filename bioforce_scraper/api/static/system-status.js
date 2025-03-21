/**
 * Indicateur de statut du système Bioforce
 * Version 1.0.0
 */

class SystemStatusIndicator {
    constructor(elementId, options = {}) {
        // Configuration par défaut
        this.defaults = {
            refreshInterval: 60000, // Intervalle de rafraîchissement en ms (1 minute)
            apiUrl: '/system-status', // URL de l'API de statut relative
            corsProxy: 'https://corsproxy.io/?', // Proxy CORS pour contourner les problèmes d'accès
            useCorsProxy: true, // Activer le proxy CORS par défaut
            statusLabels: {
                green: 'Tous les systèmes opérationnels',
                yellow: 'Dégradation de performance',
                red: 'Problèmes majeurs détectés'
            },
            onStatusChange: null // Callback lors d'un changement de statut
        };
        
        // Fusion des options utilisateur avec les options par défaut
        this.options = {...this.defaults, ...options};
        
        // Création ou récupération de l'élément DOM pour l'indicateur
        if (typeof elementId === 'string') {
            this.element = document.getElementById(elementId);
            if (!this.element) {
                console.error(`Élément avec l'ID "${elementId}" non trouvé.`);
                return;
            }
        } else if (elementId instanceof HTMLElement) {
            this.element = elementId;
        } else {
            console.error('Élément invalide fourni pour SystemStatusIndicator');
            return;
        }
        
        // Initialisation de l'interface
        this.init();
    }
    
    /**
     * Initialise l'indicateur de statut
     */
    init() {
        // Création de la structure HTML de l'indicateur
        this.element.classList.add('system-status-indicator');
        
        // Structure HTML de l'indicateur
        this.element.innerHTML = `
            <div class="status-dot"></div>
            <div class="status-text">Vérification du statut...</div>
            <div class="status-details" style="display: none;"></div>
        `;
        
        // Récupération des éléments DOM
        this.dotElement = this.element.querySelector('.status-dot');
        this.textElement = this.element.querySelector('.status-text');
        this.detailsElement = this.element.querySelector('.status-details');
        
        // Gestion du clic pour afficher/masquer les détails
        this.element.addEventListener('click', () => {
            this.toggleDetails();
        });
        
        // Premier chargement du statut
        this.refresh();
        
        // Configuration du rafraîchissement automatique
        if (this.options.refreshInterval > 0) {
            this.refreshTimer = setInterval(() => this.refresh(), this.options.refreshInterval);
        }
    }
    
    /**
     * Prépare l'URL de l'API avec ou sans proxy CORS
     */
    getApiUrl() {
        let apiUrl = this.options.apiUrl;
        
        // Si l'URL n'est pas absolue, la rendre absolue
        if (!apiUrl.startsWith('http')) {
            // Détermine si nous sommes en production ou en développement
            const isProd = window.location.hostname.includes('render.com');
            const baseUrl = isProd 
                ? 'https://bioforce-admin.onrender.com' 
                : window.location.origin;
            
            apiUrl = `${baseUrl}${apiUrl.startsWith('/') ? '' : '/'}${apiUrl}`;
        }
        
        // Utiliser le proxy CORS si nécessaire
        if (this.options.useCorsProxy) {
            return `${this.options.corsProxy}${encodeURIComponent(apiUrl)}`;
        }
        
        return apiUrl;
    }
    
    /**
     * Rafraîchit le statut du système
     */
    async refresh() {
        try {
            const apiUrl = this.getApiUrl();
            console.log('Récupération du statut depuis:', apiUrl);
            
            const response = await fetch(apiUrl, {
                headers: {
                    'Accept': 'application/json',
                    'Origin': window.location.origin
                }
            });
            
            if (!response.ok) {
                throw new Error(`Erreur HTTP: ${response.status}`);
            }
            
            const data = await response.json();
            this.updateStatus(data);
        } catch (error) {
            console.error('Erreur lors de la récupération du statut:', error);
            this.setStatus('red', 'Impossible de contacter le serveur');
            this.updateDetails({
                error: true,
                message: `Erreur: ${error.message}`,
                services: {}
            });
        }
    }
    
    /**
     * Met à jour l'indicateur avec les données de statut
     */
    updateStatus(statusData) {
        if (!statusData || typeof statusData !== 'object') {
            this.setStatus('red', 'Format de statut invalide');
            return;
        }
        
        const status = statusData.status || 'red';
        const statusLabel = this.options.statusLabels[status] || statusData.message || 'Statut inconnu';
        
        this.setStatus(status, statusLabel);
        this.updateDetails(statusData);
        
        // Déclencher le callback de changement de statut si défini
        if (typeof this.options.onStatusChange === 'function') {
            this.options.onStatusChange(statusData);
        }
    }
    
    /**
     * Définit la couleur et le texte de l'indicateur
     */
    setStatus(color, text) {
        // Mise à jour de la couleur du point
        this.dotElement.className = 'status-dot';
        this.dotElement.classList.add(`status-${color}`);
        
        // Mise à jour du texte
        this.textElement.textContent = text;
    }
    
    /**
     * Met à jour les détails du statut
     */
    updateDetails(statusData) {
        if (!statusData.services) {
            this.detailsElement.innerHTML = '<p>Aucun détail disponible</p>';
            return;
        }
        
        let detailsHtml = '<div class="status-services">';
        
        // Génération du HTML pour chaque service
        for (const [serviceName, serviceStatus] of Object.entries(statusData.services)) {
            const serviceColor = serviceStatus.status || 'red';
            const serviceMessage = serviceStatus.message || 'Statut inconnu';
            
            detailsHtml += `
                <div class="service-status">
                    <div class="service-dot status-${serviceColor}"></div>
                    <div class="service-name">${serviceName}</div>
                    <div class="service-message">${serviceMessage}</div>
                </div>
            `;
        }
        
        detailsHtml += '</div>';
        
        // Ajout d'informations supplémentaires si disponibles
        if (statusData.timestamp) {
            const date = new Date(statusData.timestamp);
            detailsHtml += `<div class="status-timestamp">Dernière mise à jour: ${date.toLocaleString()}</div>`;
        }
        
        this.detailsElement.innerHTML = detailsHtml;
    }
    
    /**
     * Affiche ou masque les détails du statut
     */
    toggleDetails() {
        const isHidden = this.detailsElement.style.display === 'none';
        this.detailsElement.style.display = isHidden ? 'block' : 'none';
    }
    
    /**
     * Arrête le rafraîchissement automatique
     */
    stop() {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
            this.refreshTimer = null;
        }
    }
}

// Si nous sommes dans un environnement de navigateur, exposer la classe globalement
if (typeof window !== 'undefined') {
    window.SystemStatusIndicator = SystemStatusIndicator;
}
