/**
 * Script pour l'interface d'administration Bioforce
 * Permet l'interaction avec l'API Bioforce pour les fonctionnalités d'administration
 */

// Configuration de base
// const API_BASE_URL = "https://bioforce-admin.onrender.com"; // URL de l'API en production
// Pour le développement local, décommentez la ligne ci-dessous et commentez celle au-dessus
const API_BASE_URL = window.location.origin; // URL de base de l'API (même domaine)

// Nouveaux endpoints correspondant à la structure de l'API bioforce-admin
const API_ENDPOINTS = {
    systemInfo: '/api/system/info',
    qdrantStats: '/api/qdrant/stats',
    gitUpdate: '/api/system/update',
    scrapeFaq: '/api/scraper/faq',
    scrapeFull: '/api/scraper/full',
    logs: '/api/system/logs',
    status: '/api/system/status'
};

// État global
let systemStatus = {
    server: false,
    scraping: false,
    qdrant: false
};

// Initialisation au chargement de la page
document.addEventListener('DOMContentLoaded', () => {
    // Récupération des informations système
    fetchSystemInfo();
    
    // Vérification de l'état des services
    checkStatus();
    
    // Récupération des statistiques Qdrant
    refreshQdrantStats();
    
    // Événements pour les boutons
    setupEventListeners();
});

/**
 * Récupère les informations système depuis l'API
 */
async function fetchSystemInfo() {
    try {
        const response = await fetch(`${API_BASE_URL}${API_ENDPOINTS.systemInfo}`);
        if (!response.ok) throw new Error(`Erreur HTTP ${response.status}`);
        
        const data = await response.json();
        
        // Mise à jour des informations système
        document.getElementById('systemVersion').textContent = data.version || '-';
        document.getElementById('pythonVersion').textContent = data.python_version || '-';
        document.getElementById('platformInfo').textContent = data.platform || '-';
        document.getElementById('currentTime').textContent = data.current_time || '-';
        document.getElementById('footerVersion').textContent = data.version || '-';
        
        // Mise à jour du lien GitHub
        const githubLink = document.getElementById('githubRepoLink');
        if (data.github_repo) {
            githubLink.href = data.github_repo;
            githubLink.textContent = data.github_repo;
        }
        
        return data;
    } catch (error) {
        console.error('Erreur lors de la récupération des informations système:', error);
        addLogMessage('systemLogs', `Erreur: ${error.message}`, 'error');
        return null;
    }
}

/**
 * Vérifie l'état des différents services
 */
async function checkStatus() {
    try {
        const response = await fetch(`${API_BASE_URL}${API_ENDPOINTS.status}`);
        if (!response.ok) throw new Error(`Erreur HTTP ${response.status}`);
        
        const data = await response.json();
        
        // Mise à jour de l'état du serveur
        updateStatusIndicator('serverStatus', 'serverStatusText', 
            data.server_status === 'ok', 
            data.server_status === 'ok' ? 'En ligne' : 'Hors ligne');
        
        // Mise à jour de l'état du scraping
        updateStatusIndicator('scrapingStatus', 'scrapingStatusText', 
            data.scraping_status === 'ready', 
            data.scraping_status === 'ready' ? 'Prêt' : 
            data.scraping_status === 'running' ? 'En cours' : 'Erreur');
        
        // Mise à jour de l'état de Qdrant
        updateStatusIndicator('qdrantStatus', 'qdrantStatusText', 
            data.qdrant_status === 'connected', 
            data.qdrant_status === 'connected' ? 'Connecté' : 'Non connecté');
        
        // Mise à jour de l'état global
        systemStatus.server = data.server_status === 'ok';
        systemStatus.scraping = data.scraping_status === 'ready';
        systemStatus.qdrant = data.qdrant_status === 'connected';
        
        // Mise à jour de la dernière vérification
        document.getElementById('lastUpdateTime').textContent = new Date().toLocaleString();
        
        return data;
    } catch (error) {
        console.error('Erreur lors de la vérification des services:', error);
        addLogMessage('systemLogs', `Erreur de vérification des services: ${error.message}`, 'error');
        
        // En cas d'erreur, on met tout en état d'erreur
        updateStatusIndicator('serverStatus', 'serverStatusText', false, 'Erreur de connexion');
        updateStatusIndicator('scrapingStatus', 'scrapingStatusText', false, 'Erreur de connexion');
        updateStatusIndicator('qdrantStatus', 'qdrantStatusText', false, 'Erreur de connexion');
        
        return null;
    }
}

/**
 * Met à jour les statistiques Qdrant
 */
async function refreshQdrantStats() {
    try {
        const response = await fetch(`${API_BASE_URL}${API_ENDPOINTS.qdrantStats}`);
        if (!response.ok) throw new Error(`Erreur HTTP ${response.status}`);
        
        const data = await response.json();
        
        // Génération du HTML pour afficher les stats
        let statsHtml = '<div class="table-responsive">';
        statsHtml += '<table class="table table-sm">';
        statsHtml += '<thead><tr><th>Collection</th><th>Points</th><th>Segments</th><th>RAM (MB)</th></tr></thead>';
        statsHtml += '<tbody>';
        
        for (const collection in data) {
            if (data.hasOwnProperty(collection)) {
                const stats = data[collection];
                statsHtml += `<tr>
                    <td>${collection}</td>
                    <td>${stats.vectors_count || 0}</td>
                    <td>${stats.segments_count || 0}</td>
                    <td>${Math.round((stats.ram_usage || 0) / (1024 * 1024))}</td>
                </tr>`;
            }
        }
        
        statsHtml += '</tbody></table></div>';
        
        // Mise à jour de l'élément HTML
        document.getElementById('qdrantStats').innerHTML = statsHtml;
        
        return data;
    } catch (error) {
        console.error('Erreur lors de la récupération des statistiques Qdrant:', error);
        document.getElementById('qdrantStats').innerHTML = 
            `<div class="alert alert-danger">Erreur: ${error.message}</div>`;
        return null;
    }
}

/**
 * Lance une mise à jour depuis GitHub
 */
async function updateFromGithub() {
    try {
        addLogMessage('githubLogs', 'Démarrage de la mise à jour depuis GitHub...', 'info');
        
        const response = await fetch(`${API_BASE_URL}${API_ENDPOINTS.gitUpdate}`, {
            method: 'POST'
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || `Erreur HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        // Ajout des logs de mise à jour
        addLogMessage('githubLogs', 'Mise à jour démarrée avec succès', 'success');
        
        if (data.output) {
            data.output.forEach(line => {
                addLogMessage('githubLogs', line);
            });
        }
        
        // Mise à jour des informations système après une mise à jour réussie
        setTimeout(fetchSystemInfo, 2000);
        
        return data;
    } catch (error) {
        console.error('Erreur lors de la mise à jour depuis GitHub:', error);
        addLogMessage('githubLogs', `Erreur: ${error.message}`, 'error');
        return null;
    }
}

/**
 * Lance un scraping FAQ
 */
async function runFaqScraping(forceUpdate = false) {
    try {
        addLogMessage('scrapingLogs', 'Démarrage du scraping FAQ...', 'info');
        
        const response = await fetch(`${API_BASE_URL}${API_ENDPOINTS.scrapeFaq}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ force_update: forceUpdate })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || `Erreur HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        // Ajout des logs de scraping
        addLogMessage('scrapingLogs', 'Scraping FAQ démarré avec succès', 'success');
        
        return data;
    } catch (error) {
        console.error('Erreur lors du scraping FAQ:', error);
        addLogMessage('scrapingLogs', `Erreur: ${error.message}`, 'error');
        return null;
    }
}

/**
 * Lance un scraping du site complet
 */
async function runFullScraping(forceUpdate = false) {
    try {
        addLogMessage('scrapingLogs', 'Démarrage du scraping complet...', 'info');
        
        const response = await fetch(`${API_BASE_URL}${API_ENDPOINTS.scrapeFull}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ force_update: forceUpdate })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || `Erreur HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        // Ajout des logs de scraping
        addLogMessage('scrapingLogs', 'Scraping complet démarré avec succès', 'success');
        
        return data;
    } catch (error) {
        console.error('Erreur lors du scraping complet:', error);
        addLogMessage('scrapingLogs', `Erreur: ${error.message}`, 'error');
        return null;
    }
}

/**
 * Met à jour un indicateur de statut
 */
function updateStatusIndicator(indicatorId, textId, isGood, text) {
    const indicator = document.getElementById(indicatorId);
    const textElement = document.getElementById(textId);
    
    if (indicator) {
        indicator.className = 'status-indicator';
        indicator.classList.add(isGood ? 'status-good' : 'status-error');
    }
    
    if (textElement) {
        textElement.textContent = text;
    }
}

/**
 * Ajoute un message de log à un conteneur spécifié
 */
function addLogMessage(containerId, message, type = 'info') {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    const timestamp = new Date().toLocaleTimeString();
    const logClass = type === 'error' ? 'text-danger' : 
                    type === 'success' ? 'text-success' : 
                    type === 'warning' ? 'text-warning' : 'text-light';
    
    const logEntry = document.createElement('div');
    logEntry.className = logClass;
    logEntry.innerHTML = `[${timestamp}] ${message}`;
    
    container.appendChild(logEntry);
    container.scrollTop = container.scrollHeight;
}

/**
 * Configure les écouteurs d'événements pour l'interface
 */
function setupEventListeners() {
    // Bouton de vérification de statut
    document.getElementById('checkStatusBtn').addEventListener('click', () => {
        checkStatus();
    });
    
    // Bouton de rafraîchissement des stats Qdrant
    document.getElementById('refreshQdrantStats').addEventListener('click', () => {
        refreshQdrantStats();
    });
    
    // Bouton de vérification de la connexion Qdrant
    document.getElementById('checkQdrantBtn').addEventListener('click', () => {
        addLogMessage('systemLogs', 'Vérification de la connexion Qdrant...', 'info');
        checkStatus();
    });
    
    // Bouton de mise à jour GitHub
    document.getElementById('updateFromGithub').addEventListener('click', () => {
        updateFromGithub();
    });
    
    // Formulaire de scraping FAQ
    document.getElementById('faqScraperForm').addEventListener('submit', (e) => {
        e.preventDefault();
        const forceUpdate = document.getElementById('forceFaqUpdate').checked;
        runFaqScraping(forceUpdate);
    });
    
    // Formulaire de scraping complet
    document.getElementById('fullScraperForm').addEventListener('submit', (e) => {
        e.preventDefault();
        const forceUpdate = document.getElementById('forceFullUpdate').checked;
        runFullScraping(forceUpdate);
    });
    
    // Bouton de rafraîchissement des logs
    document.getElementById('refreshLogs').addEventListener('click', () => {
        // TODO: Implémenter la récupération des logs système
        addLogMessage('systemLogs', 'Rafraîchissement des logs...', 'info');
    });
    
    // Bouton de rafraîchissement de la page
    document.getElementById('refreshPage').addEventListener('click', () => {
        window.location.reload();
    });
}
