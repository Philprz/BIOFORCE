/**
 * Script pour l'interface d'administration Bioforce
 * Permet l'interaction avec l'API Bioforce pour les fonctionnalités d'administration
 */

// Configuration de base
const API_BASE_URL = "https://bioforce-interface.onrender.com"; // URL de l'API en production
// Pour le développement local, décommentez la ligne ci-dessous et commentez celle au-dessus
// const API_BASE_URL = window.location.origin; // URL de base de l'API (même domaine)

const API_ENDPOINTS = {
    systemInfo: '/api/admin/system-info',
    qdrantStats: '/api/admin/qdrant-stats',
    gitUpdate: '/api/admin/git-update',
    scrapeFaq: '/api/scrape/faq',
    scrapeFull: '/api/scrape/full',
    logs: '/api/admin/logs',
    status: '/api/admin/status'
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
        systemStatus = {
            server: data.server_status === 'ok',
            scraping: data.scraping_status === 'ready',
            qdrant: data.qdrant_status === 'connected'
        };
        
        // Activation/désactivation des boutons en fonction de l'état
        const scrapingFaqButtons = document.querySelectorAll('[data-action="scrape-faq"]');
        const scrapingFullButtons = document.querySelectorAll('[data-action="scrape-full"]');
        const gitUpdateButton = document.getElementById('updateFromGithub');
        
        scrapingFaqButtons.forEach(btn => btn.disabled = !systemStatus.server);
        scrapingFullButtons.forEach(btn => btn.disabled = !systemStatus.server);
        if (gitUpdateButton) gitUpdateButton.disabled = !systemStatus.server;
        
        // Mise à jour de la dernière vérification
        document.getElementById('lastUpdateTime').textContent = new Date().toLocaleString();
        
        return data;
    } catch (error) {
        console.error('Erreur lors de la vérification du statut:', error);
        // En cas d'erreur, tous les services sont considérés comme hors ligne
        updateStatusIndicator('serverStatus', 'serverStatusText', false, 'Erreur de connexion');
        updateStatusIndicator('scrapingStatus', 'scrapingStatusText', false, 'Erreur de connexion');
        updateStatusIndicator('qdrantStatus', 'qdrantStatusText', false, 'Erreur de connexion');
        
        systemStatus = {
            server: false,
            scraping: false,
            qdrant: false
        };
        
        // Désactivation de tous les boutons d'action
        const scrapingFaqButtons = document.querySelectorAll('[data-action="scrape-faq"]');
        const scrapingFullButtons = document.querySelectorAll('[data-action="scrape-full"]');
        const gitUpdateButton = document.getElementById('updateFromGithub');
        
        scrapingFaqButtons.forEach(btn => btn.disabled = true);
        scrapingFullButtons.forEach(btn => btn.disabled = true);
        if (gitUpdateButton) gitUpdateButton.disabled = true;
        
        // Mise à jour de la dernière vérification
        document.getElementById('lastUpdateTime').textContent = new Date().toLocaleString() + ' (échec)';
        
        addLogMessage('systemLogs', `Erreur de connexion à l'API: ${error.message}`, 'error');
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
    // Bouton de vérification du statut
    document.getElementById('checkStatusBtn').addEventListener('click', checkStatus);
    
    // Boutons de scraping
    document.querySelectorAll('[data-action="scrape-faq"]').forEach(btn => {
        btn.addEventListener('click', () => runFaqScraping(btn.dataset.forceUpdate === 'true'));
    });
    
    document.querySelectorAll('[data-action="scrape-full"]').forEach(btn => {
        btn.addEventListener('click', () => runFullScraping(btn.dataset.forceUpdate === 'true'));
    });
    
    // Bouton de rafraîchissement des statistiques Qdrant
    document.getElementById('refreshQdrantStats').addEventListener('click', refreshQdrantStats);
    
    // Bouton de mise à jour depuis GitHub
    document.getElementById('updateFromGithub').addEventListener('click', updateFromGithub);
    
    // Bouton de rafraîchissement global
    document.getElementById('refreshBtn').addEventListener('click', () => {
        checkStatus();
        refreshQdrantStats();
        addLogMessage('systemLogs', 'Actualisation manuelle déclenchée', 'info');
    });
    
    // Bouton de rafraîchissement des logs
    document.getElementById('refreshLogs').addEventListener('click', () => {
        fetchLogs();
    });
    
    // Action sur des boutons Qdrant spécifiques
    const checkQdrantBtn = document.getElementById('checkQdrantBtn');
    if (checkQdrantBtn) {
        checkQdrantBtn.addEventListener('click', () => {
            addLogMessage('systemLogs', 'Vérification de la connexion Qdrant...', 'info');
            fetch(`${API_BASE_URL}${API_ENDPOINTS.qdrantStats}`)
                .then(response => response.json())
                .then(data => {
                    addLogMessage('systemLogs', `Vérification Qdrant: ${data.status || 'OK'}`, 'success');
                })
                .catch(error => {
                    addLogMessage('systemLogs', `Erreur Qdrant: ${error.message}`, 'error');
                });
        });
    }
    
    const optimizeQdrantBtn = document.getElementById('optimizeQdrantBtn');
    if (optimizeQdrantBtn) {
        optimizeQdrantBtn.addEventListener('click', () => {
            addLogMessage('systemLogs', 'Optimisation de Qdrant en cours...', 'info');
            fetch(`${API_BASE_URL}${API_ENDPOINTS.qdrantStats}?action=optimize`, { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    addLogMessage('systemLogs', `Optimisation Qdrant: ${data.status || 'Terminée'}`, 'success');
                })
                .catch(error => {
                    addLogMessage('systemLogs', `Erreur d'optimisation: ${error.message}`, 'error');
                });
        });
    }
}