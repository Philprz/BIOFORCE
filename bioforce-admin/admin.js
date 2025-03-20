/**
 * Script pour l'interface d'administration Bioforce
 * Permet l'interaction avec l'API Bioforce pour les fonctionnalités d'administration
 */

// Configuration de base
const API_LOCAL = 'http://localhost:8000';
const API_PRODUCTION = 'https://bioforce-interface.onrender.com';
const USE_PRODUCTION_API = window.location.hostname.includes('render.com');
const API_BASE_URL = USE_PRODUCTION_API ? API_PRODUCTION : API_LOCAL;

// Activer les logs détaillés
const DEBUG_MODE = true;

/**
 * Log détaillé pour le débogage
 * @param {string} message - Message à logger
 * @param {string} type - Type de log (info, error, warning)
 * @param {any} data - Données supplémentaires à logger
 */
function debugLog(message, type = 'info', data = null) {
    if (!DEBUG_MODE) return;
    
    const timestamp = new Date().toISOString();
    const prefix = `[${timestamp}] [ADMIN]`;
    
    switch (type) {
        case 'error':
            console.error(`${prefix} ERROR:`, message, data ? data : '');
            break;
        case 'warning':
            console.warn(`${prefix} WARNING:`, message, data ? data : '');
            break;
        default:
            console.log(`${prefix} INFO:`, message, data ? data : '');
    }
    
    // Ajouter également au journal système dans l'interface
    addLogMessage('systemLogs', `${message}${data ? ': ' + JSON.stringify(data) : ''}`, type);
}

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
        
        debugLog('Informations système récupérées avec succès', 'info', data);
        
        return data;
    } catch (error) {
        console.error('Erreur lors de la récupération des informations système:', error);
        addLogMessage('systemLogs', `Erreur: ${error.message}`, 'error');
        debugLog('Erreur lors de la récupération des informations système', 'error', error);
        return null;
    }
}

/**
 * Vérifie l'état de tous les services
 */
async function checkStatus() {
    try {
        debugLog('Vérification du statut des services...', 'info');
        
        // Affichage du statut "Vérification en cours..."
        ['server', 'scraping', 'qdrant'].forEach(service => {
            const statusElement = document.getElementById(`${service}Status`);
            if (statusElement) {
                statusElement.innerHTML = '<span class="badge bg-warning text-dark">Vérification en cours...</span>';
            }
        });
        
        const response = await fetch(`${API_BASE_URL}${API_ENDPOINTS.status}`);
        
        if (!response.ok) {
            throw new Error(`Erreur HTTP ${response.status}`);
        }
        
        const data = await response.json();
        debugLog('Réponse API de statut reçue', 'info', data);
        
        // Mise à jour du statut dans l'interface avec le nouveau format de réponse
        const services = ['server', 'scraping', 'qdrant'];
        
        services.forEach(service => {
            if (data[service]) {
                const serviceData = data[service];
                const isOk = serviceData.status === 'ok';
                systemStatus[service] = isOk;
                
                const statusElement = document.getElementById(`${service}Status`);
                if (statusElement) {
                    if (isOk) {
                        statusElement.innerHTML = '<span class="badge bg-success">Connecté</span>';
                    } else if (serviceData.status === 'warning') {
                        statusElement.innerHTML = `<span class="badge bg-warning text-dark">Attention</span>
                                                <div class="small text-muted mt-1">${serviceData.message || 'Aucun détail'}</div>`;
                        // Enregistrer l'avertissement dans les logs
                        debugLog(`Avertissement pour ${service}`, 'warning', serviceData);
                    } else {
                        statusElement.innerHTML = `<span class="badge bg-danger">Erreur de connexion</span>
                                                <div class="small text-muted mt-1">${serviceData.message || 'Aucun détail'}</div>`;
                        // Enregistrer l'erreur dans les logs
                        debugLog(`Erreur de connexion pour ${service}`, 'error', serviceData);
                    }
                }
            }
        });
        
        // Log détaillé pour le statut de Qdrant
        if (data.qdrant) {
            debugLog(`Statut Qdrant détaillé:`, 'info', data.qdrant);
            
            // Afficher les détails de connexion Qdrant dans la section dédiée
            const qdrantDetailsElement = document.getElementById('qdrantConnectionDetails');
            if (qdrantDetailsElement && data.qdrant.details) {
                const details = data.qdrant.details;
                qdrantDetailsElement.innerHTML = `
                    <div class="card mb-3">
                        <div class="card-header">Détails de connexion Qdrant</div>
                        <div class="card-body">
                            <p><strong>Host:</strong> ${details.host || 'Non disponible'}</p>
                            <p><strong>Port:</strong> ${details.port || 'Non disponible'}</p>
                            <p><strong>Collection:</strong> ${details.collection || 'Non disponible'}</p>
                            <p><strong>API Key fournie:</strong> ${details.api_key_provided ? 'Oui' : 'Non'}</p>
                            <p><strong>Collections trouvées:</strong> ${details.collections_found || 'Non disponible'}</p>
                            ${details.collections_list ? `<p><strong>Liste des collections:</strong> ${details.collections_list.join(', ')}</p>` : ''}
                            <p><strong>Dernière tentative:</strong> ${details.connection_attempt_time || 'Non disponible'}</p>
                        </div>
                    </div>
                `;
            }
        }
        
        // Vérification approfondie de Qdrant (test direct)
        try {
            debugLog('Vérification directe de Qdrant...', 'info');
            const qdrantDirectResponse = await fetch(`${API_BASE_URL}${API_ENDPOINTS.qdrantStats}`);
            const qdrantDirectData = await qdrantDirectResponse.json();
            
            debugLog('Réponse directe de Qdrant', 'info', qdrantDirectData);
            
            // Si la vérification directe réussit mais que le statut global indique une erreur
            if (qdrantDirectData && qdrantDirectData.status === 'success' && !systemStatus.qdrant) {
                debugLog('Incohérence détectée: Qdrant répond directement mais le statut indique une erreur', 'warning', {
                    statusAPI: data.qdrant,
                    directAPI: qdrantDirectData
                });
                
                // Mettre à jour manuellement le statut dans l'interface
                const qdrantStatusElement = document.getElementById('qdrantStatus');
                if (qdrantStatusElement) {
                    qdrantStatusElement.innerHTML = '<span class="badge bg-warning text-dark">État incohérent</span>' +
                        '<div class="small text-muted mt-1">L\'API indique une erreur mais Qdrant répond. Vérifiez la configuration.</div>';
                }
                
                // Ajouter une alerte spécifique pour l'incohérence
                addLogMessage('systemLogs', 'Incohérence détectée: Qdrant répond directement mais le statut global indique une erreur', 'warning');
            }
        } catch (qdrantError) {
            debugLog('Échec de la vérification directe de Qdrant', 'error', qdrantError);
        }
        
        // Mise à jour de la dernière vérification
        document.getElementById('lastUpdateTime').textContent = new Date().toLocaleString();
        
        debugLog('État des services vérifié avec succès', 'info', data);
        
        return data;
    } catch (error) {
        console.error('Erreur lors de la vérification du statut:', error);
        
        // Mise à jour du statut en cas d'erreur
        ['server', 'scraping', 'qdrant'].forEach(service => {
            systemStatus[service] = false;
            
            const statusElement = document.getElementById(`${service}Status`);
            if (statusElement) {
                statusElement.innerHTML = '<span class="badge bg-danger">Erreur de connexion</span>';
            }
        });
        
        // Ajout d'informations sur l'erreur
        const serverStatusElement = document.getElementById('serverStatus');
        if (serverStatusElement) {
            serverStatusElement.innerHTML = `
                <span class="badge bg-danger">Erreur de connexion</span>
                <div class="small text-muted mt-1">
                    ${error.message}
                    <br>
                    API URL: ${API_BASE_URL}${API_ENDPOINTS.status}
                    <br>
                    Environnement: ${USE_PRODUCTION_API ? 'Production' : 'Local'}
                </div>
            `;
        }
        
        // Mise à jour de la dernière vérification
        document.getElementById('lastUpdateTime').textContent = new Date().toLocaleString() + ' (échec)';
        
        addLogMessage('systemLogs', `Erreur de connexion à l'API: ${error.message}`, 'error');
        debugLog('Erreur lors de la vérification du statut', 'error', {
            error: error.message,
            apiUrl: `${API_BASE_URL}${API_ENDPOINTS.status}`,
            environment: USE_PRODUCTION_API ? 'Production' : 'Local'
        });
        return null;
    }
}

/**
 * Récupère et affiche les statistiques de Qdrant
 */
async function refreshQdrantStats() {
    try {
        debugLog('Récupération des statistiques Qdrant...', 'info');
        const response = await fetch(`${API_BASE_URL}${API_ENDPOINTS.qdrantStats}`);
        
        if (!response.ok) {
            throw new Error(`Erreur HTTP ${response.status}`);
        }
        
        const data = await response.json();
        debugLog('Réponse des stats Qdrant reçue', 'info', data);
        
        let statsHtml = '';
        let logsHtml = '';
        
        // Affichage des logs de débogage s'ils sont présents
        if (data.debug_logs && data.debug_logs.length > 0) {
            logsHtml = `
                <div class="card mb-3">
                    <div class="card-header">
                        <i class="bi bi-journal-text"></i> Logs de diagnostic (${data.debug_logs.length})
                        <button class="btn btn-sm btn-outline-secondary float-end" id="toggleLogsButton">
                            Afficher/Masquer
                        </button>
                    </div>
                    <div class="card-body p-0" id="qdrantLogsContainer" style="display: none; max-height: 300px; overflow-y: auto;">
                        <table class="table table-sm mb-0">
                            <thead>
                                <tr>
                                    <th>Timestamp</th>
                                    <th>Niveau</th>
                                    <th>Message</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${data.debug_logs.map(log => `
                                    <tr class="${log.level === 'error' ? 'table-danger' : log.level === 'warning' ? 'table-warning' : ''}">
                                        <td><small>${log.timestamp}</small></td>
                                        <td><span class="badge ${log.level === 'error' ? 'bg-danger' : log.level === 'warning' ? 'bg-warning text-dark' : 'bg-info'}">${log.level}</span></td>
                                        <td>
                                            ${log.message}
                                            ${log.data ? `<a href="#" class="small log-data-toggle" data-log-id="${log.timestamp}">Détails</a>
                                                <pre class="log-data mt-1" id="log-data-${log.timestamp}" style="display: none;">${JSON.stringify(log.data, null, 2)}</pre>` : ''}
                                        </td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>
            `;
            
            // Ajouter les logs au journal global du système
            data.debug_logs.forEach(log => {
                addLogMessage('systemLogs', `[Qdrant] ${log.message}`, log.level);
            });
        }
        
        // Affichage des statistiques générales
        if (data.status === 'success') {
            const connectionInfo = data.connection || {};
            const statsData = data.data || {};
            
            statsHtml += `
                <div class="alert alert-success">
                    <i class="bi bi-check-circle-fill"></i> Qdrant est connecté et opérationnel
                    <p class="small text-muted mb-0 mt-1">${data.message || ''}</p>
                </div>
                
                <div class="card mb-3">
                    <div class="card-header"><i class="bi bi-diagram-3"></i> Informations sur la collection</div>
                    <div class="card-body">
                        <p><strong>URL:</strong> ${connectionInfo.url || 'Non spécifié'}</p>
                        <p><strong>Nom de la collection:</strong> ${connectionInfo.collection || 'Non spécifié'}</p>
                        <p><strong>Dernière vérification:</strong> ${connectionInfo.timestamp ? new Date(connectionInfo.timestamp).toLocaleString() : 'Non spécifié'}</p>
                    </div>
                </div>
                
                <div class="card mb-3">
                    <div class="card-header"><i class="bi bi-graph-up"></i> Statistiques de la collection</div>
                    <div class="card-body">
                        <p><strong>Vecteurs:</strong> ${statsData.vectors_count || 0}</p>
                        <p><strong>Points:</strong> ${statsData.points_count || 0}</p>
                        <p><strong>Segments:</strong> ${statsData.segments_count || 0}</p>
                        <p><strong>Segments OK:</strong> ${statsData.segments_ok || 0}</p>
                        <p><strong>Segments en échec:</strong> ${statsData.segments_failed || 0}</p>
                    </div>
                </div>
            `;
            
            // Ajouter des diagnostics détaillés si disponibles
            if (data.connection && data.connection.diagnostics && data.connection.diagnostics.collection_info) {
                const collectionInfo = data.connection.diagnostics.collection_info;
                
                statsHtml += `
                    <div class="card mb-3">
                        <div class="card-header"><i class="bi bi-gear"></i> Configuration de la collection</div>
                        <div class="card-body">
                            <p><strong>Taille des vecteurs:</strong> ${collectionInfo.config?.params?.vectors?.size || 'Non disponible'}</p>
                            <p><strong>Métrique de distance:</strong> ${collectionInfo.config?.params?.vectors?.distance || 'Non disponible'}</p>
                            <p><strong>Status collection:</strong> ${collectionInfo.status || 'Non disponible'}</p>
                        </div>
                    </div>
                `;
            }
            
            // Enregistrer dans les logs que Qdrant est connecté
            debugLog('Qdrant connecté et opérationnel', 'info', {
                url: connectionInfo.url,
                collection: connectionInfo.collection,
                data: statsData
            });
        } else {
            // En cas d'erreur, afficher les détails du diagnostic
            statsHtml = `
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle-fill"></i> Erreur de connexion à Qdrant
                    <p class="mt-2 mb-0">${data.message || 'Aucun détail disponible sur l\'erreur'}</p>
                </div>
            `;
            
            // Afficher les détails de connexion s'ils sont disponibles
            if (data.connection) {
                statsHtml += `
                    <div class="card mb-3">
                        <div class="card-header"><i class="bi bi-info-circle"></i> Informations de connexion</div>
                        <div class="card-body">
                            <p><strong>URL:</strong> ${data.connection.url || 'Non disponible'}</p>
                            <p><strong>Collection:</strong> ${data.connection.collection || 'Non disponible'}</p>
                            <p><strong>Client initialisé:</strong> ${data.connection.client_initialized ? 'Oui' : 'Non'}</p>
                            <p><strong>Timestamp:</strong> ${data.timestamp || 'Non disponible'}</p>
                        </div>
                    </div>
                `;
            }
            
            // Afficher les détails de diagnostic des erreurs
            if (data.connection && data.connection.diagnostics) {
                const diag = data.connection.diagnostics;
                
                if (diag.collection_error) {
                    statsHtml += `
                        <div class="card mb-3 border-danger">
                            <div class="card-header bg-danger text-white"><i class="bi bi-bug"></i> Erreur de collection</div>
                            <div class="card-body">
                                <p><strong>Type:</strong> ${diag.collection_error.error_type || 'Non disponible'}</p>
                                <p><strong>Message:</strong> ${diag.collection_error.error_message || 'Non disponible'}</p>
                                <div class="mt-2">
                                    <button class="btn btn-sm btn-outline-secondary" type="button" data-bs-toggle="collapse" data-bs-target="#collapseTracebackCollection">
                                        Afficher la trace d'erreur
                                    </button>
                                    <div class="collapse mt-2" id="collapseTracebackCollection">
                                        <div class="card card-body">
                                            <pre class="mb-0" style="max-height: 200px; overflow-y: auto;">${diag.collection_error.traceback || 'Non disponible'}</pre>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    `;
                }
                
                if (diag.stats_error) {
                    statsHtml += `
                        <div class="card mb-3 border-danger">
                            <div class="card-header bg-danger text-white"><i class="bi bi-bug"></i> Erreur de statistiques</div>
                            <div class="card-body">
                                <p><strong>Type:</strong> ${diag.stats_error.error_type || 'Non disponible'}</p>
                                <p><strong>Message:</strong> ${diag.stats_error.error_message || 'Non disponible'}</p>
                                <div class="mt-2">
                                    <button class="btn btn-sm btn-outline-secondary" type="button" data-bs-toggle="collapse" data-bs-target="#collapseTracebackStats">
                                        Afficher la trace d'erreur
                                    </button>
                                    <div class="collapse mt-2" id="collapseTracebackStats">
                                        <div class="card card-body">
                                            <pre class="mb-0" style="max-height: 200px; overflow-y: auto;">${diag.stats_error.traceback || 'Non disponible'}</pre>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    `;
                }
            }
            
            // Enregistrer dans les logs l'erreur de connexion
            debugLog('Erreur de connexion à Qdrant', 'error', {
                message: data.message,
                response: data
            });
        }
        
        // Mise à jour de l'élément HTML
        document.getElementById('qdrantStats').innerHTML = statsHtml + logsHtml;
        
        // Ajouter les écouteurs d'événements pour les toggles
        setTimeout(() => {
            // Toggle pour afficher/masquer les logs
            const toggleLogsButton = document.getElementById('toggleLogsButton');
            if (toggleLogsButton) {
                toggleLogsButton.addEventListener('click', () => {
                    const logsContainer = document.getElementById('qdrantLogsContainer');
                    if (logsContainer) {
                        logsContainer.style.display = logsContainer.style.display === 'none' ? 'block' : 'none';
                    }
                });
            }
            
            // Toggle pour chaque détail de log
            document.querySelectorAll('.log-data-toggle').forEach(toggle => {
                toggle.addEventListener('click', (e) => {
                    e.preventDefault();
                    const logId = toggle.getAttribute('data-log-id');
                    const dataElement = document.getElementById(`log-data-${logId}`);
                    if (dataElement) {
                        dataElement.style.display = dataElement.style.display === 'none' ? 'block' : 'none';
                    }
                });
            });
        }, 100);
        
        debugLog('Statistiques Qdrant mises à jour avec succès', 'info', data);
        
        return data;
    } catch (error) {
        console.error('Erreur lors de la récupération des statistiques Qdrant:', error);
        document.getElementById('qdrantStats').innerHTML = 
            `<div class="alert alert-danger">
                <i class="bi bi-exclamation-triangle-fill"></i> Erreur: ${error.message}
                <div class="mt-2">
                    <p>URL: <code>${API_BASE_URL}${API_ENDPOINTS.qdrantStats}</code></p>
                    <p>Environnement: <code>${USE_PRODUCTION_API ? 'Production' : 'Local'}</code></p>
                </div>
            </div>`;
        debugLog('Erreur lors de la récupération des statistiques Qdrant', 'error', {
            error: error.message,
            apiUrl: `${API_BASE_URL}${API_ENDPOINTS.qdrantStats}`,
            environment: USE_PRODUCTION_API ? 'Production' : 'Local'
        });
        return null;
    }
}

/**
 * Lance une mise à jour depuis GitHub
 */
async function updateFromGithub() {
    try {
        addLogMessage('githubLogs', 'Démarrage de la mise à jour depuis GitHub...', 'info');
        debugLog('Démarrage de la mise à jour depuis GitHub', 'info');
        
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
        debugLog('Mise à jour démarrée avec succès', 'success', data);
        
        if (data.output) {
            data.output.forEach(line => {
                addLogMessage('githubLogs', line);
                debugLog(line, 'info');
            });
        }
        
        // Mise à jour des informations système après une mise à jour réussie
        setTimeout(fetchSystemInfo, 2000);
        
        return data;
    } catch (error) {
        console.error('Erreur lors de la mise à jour depuis GitHub:', error);
        addLogMessage('githubLogs', `Erreur: ${error.message}`, 'error');
        debugLog('Erreur lors de la mise à jour depuis GitHub', 'error', error);
        return null;
    }
}

/**
 * Lance un scraping FAQ
 */
async function runFaqScraping(forceUpdate = false) {
    try {
        addLogMessage('scrapingLogs', 'Démarrage du scraping FAQ...', 'info');
        debugLog('Démarrage du scraping FAQ', 'info');
        
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
        debugLog('Scraping FAQ démarré avec succès', 'success', data);
        
        return data;
    } catch (error) {
        console.error('Erreur lors du scraping FAQ:', error);
        addLogMessage('scrapingLogs', `Erreur: ${error.message}`, 'error');
        debugLog('Erreur lors du scraping FAQ', 'error', error);
        return null;
    }
}

/**
 * Lance un scraping du site complet
 */
async function runFullScraping(forceUpdate = false) {
    try {
        addLogMessage('scrapingLogs', 'Démarrage du scraping complet...', 'info');
        debugLog('Démarrage du scraping complet', 'info');
        
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
        debugLog('Scraping complet démarré avec succès', 'success', data);
        
        return data;
    } catch (error) {
        console.error('Erreur lors du scraping complet:', error);
        addLogMessage('scrapingLogs', `Erreur: ${error.message}`, 'error');
        debugLog('Erreur lors du scraping complet', 'error', error);
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
    document.getElementById('refreshQdrantBtn').addEventListener('click', refreshQdrantStats);
    
    // Bouton de mise à jour depuis GitHub
    document.getElementById('updateFromGithub').addEventListener('click', updateFromGithub);
    
    // Bouton de rafraîchissement global
    document.getElementById('refreshBtn').addEventListener('click', () => {
        checkStatus();
        refreshQdrantStats();
        addLogMessage('systemLogs', 'Actualisation manuelle déclenchée', 'info');
        debugLog('Actualisation manuelle déclenchée', 'info');
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
            debugLog('Vérification de la connexion Qdrant', 'info');
            fetch(`${API_BASE_URL}${API_ENDPOINTS.qdrantStats}`)
                .then(response => response.json())
                .then(data => {
                    addLogMessage('systemLogs', `Vérification Qdrant: ${data.status || 'OK'}`, 'success');
                    debugLog(`Vérification Qdrant: ${data.status || 'OK'}`, 'success', data);
                })
                .catch(error => {
                    addLogMessage('systemLogs', `Erreur Qdrant: ${error.message}`, 'error');
                    debugLog('Erreur Qdrant', 'error', error);
                });
        });
    }
    
    const optimizeQdrantBtn = document.getElementById('optimizeQdrantBtn');
    if (optimizeQdrantBtn) {
        optimizeQdrantBtn.addEventListener('click', () => {
            addLogMessage('systemLogs', 'Optimisation de Qdrant en cours...', 'info');
            debugLog('Optimisation de Qdrant en cours', 'info');
            fetch(`${API_BASE_URL}${API_ENDPOINTS.qdrantStats}?action=optimize`, { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    addLogMessage('systemLogs', `Optimisation Qdrant: ${data.status || 'Terminée'}`, 'success');
                    debugLog(`Optimisation Qdrant: ${data.status || 'Terminée'}`, 'success', data);
                })
                .catch(error => {
                    addLogMessage('systemLogs', `Erreur d'optimisation: ${error.message}`, 'error');
                    debugLog('Erreur d\'optimisation', 'error', error);
                });
        });
    }
    
    // Gestion des templates d'email
    const emailTemplateSelect = document.getElementById('emailTemplateSelect');
    if (emailTemplateSelect) {
        // Chargement du template au changement de sélection
        emailTemplateSelect.addEventListener('change', loadEmailTemplate);
        
        // Chargement initial du template sélectionné
        loadEmailTemplate();
        
        // Enregistrement des modifications du template
        document.getElementById('saveEmailTemplate').addEventListener('click', saveEmailTemplate);
        
        // Prévisualisation du template
        document.getElementById('previewEmailTemplate').addEventListener('click', previewEmailTemplate);
    }
}

/**
 * Charge un template d'email depuis l'API
 */
async function loadEmailTemplate() {
    const templateType = document.getElementById('emailTemplateSelect').value;
    
    try {
        addLogMessage('systemLogs', `Chargement du template d'email: ${templateType}...`, 'info');
        debugLog(`Chargement du template d'email: ${templateType}`, 'info');
        const response = await fetch(`${API_BASE_URL}${API_ENDPOINTS.emailTemplate}?type=${templateType}`);
        
        if (!response.ok) throw new Error(`Erreur HTTP ${response.status}`);
        
        const data = await response.json();
        
        // Remplissage des champs du formulaire
        document.getElementById('emailSubject').value = data.subject || '';
        document.getElementById('emailContent').value = data.content || '';
        
        addLogMessage('systemLogs', `Template d'email ${templateType} chargé avec succès`, 'success');
        debugLog(`Template d'email ${templateType} chargé avec succès`, 'success', data);
    } catch (error) {
        console.error(`Erreur lors du chargement du template d'email:`, error);
        addLogMessage('systemLogs', `Erreur de chargement du template: ${error.message}`, 'error');
        debugLog(`Erreur de chargement du template d'email: ${error.message}`, 'error', error);
    }
}

/**
 * Enregistre les modifications d'un template d'email
 */
async function saveEmailTemplate() {
    const templateType = document.getElementById('emailTemplateSelect').value;
    const subject = document.getElementById('emailSubject').value.trim();
    const content = document.getElementById('emailContent').value.trim();
    
    if (!subject || !content) {
        addLogMessage('systemLogs', 'Le sujet et le contenu du template sont obligatoires.', 'error');
        debugLog('Le sujet et le contenu du template sont obligatoires', 'error');
        return;
    }
    
    try {
        addLogMessage('systemLogs', `Enregistrement du template d'email: ${templateType}...`, 'info');
        debugLog(`Enregistrement du template d'email: ${templateType}`, 'info');
        
        const response = await fetch(`${API_BASE_URL}${API_ENDPOINTS.emailTemplate}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                type: templateType,
                subject: subject,
                content: content
            })
        });
        
        if (!response.ok) throw new Error(`Erreur HTTP ${response.status}`);
        
        const data = await response.json();
        
        addLogMessage('systemLogs', `Template d'email ${templateType} enregistré avec succès`, 'success');
        debugLog(`Template d'email ${templateType} enregistré avec succès`, 'success', data);
    } catch (error) {
        console.error(`Erreur lors de l'enregistrement du template d'email:`, error);
        addLogMessage('systemLogs', `Erreur d'enregistrement: ${error.message}`, 'error');
        debugLog(`Erreur d'enregistrement du template d'email: ${error.message}`, 'error', error);
    }
}

/**
 * Prévisualise un template d'email avec des données de test
 */
function previewEmailTemplate() {
    const subject = document.getElementById('emailSubject').value.trim();
    const content = document.getElementById('emailContent').value.trim();
    
    if (!subject || !content) {
        addLogMessage('systemLogs', 'Le sujet et le contenu du template sont obligatoires pour prévisualiser.', 'error');
        debugLog('Le sujet et le contenu du template sont obligatoires pour prévisualiser', 'error');
        return;
    }
    
    // Substitution des variables de test
    const testData = {
        nom: 'Dupont',
        prenom: 'Jean',
        email: 'jean.dupont@example.com',
        date: new Date().toLocaleDateString('fr-FR'),
        lien_confirmation: 'https://bioforce.org/confirmation/exemple'
    };
    
    let previewContent = content;
    for (const [key, value] of Object.entries(testData)) {
        const regex = new RegExp(`{{${key}}}`, 'g');
        previewContent = previewContent.replace(regex, value);
    }
    
    // Création d'une fenêtre de prévisualisation
    const previewWindow = window.open('', '_blank', 'width=800,height=600');
    previewWindow.document.write(`
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Prévisualisation - ${subject}</title>
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; margin: 20px; }
                .email-container { max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 5px; }
                .email-header { background-color: #f5f5f5; padding: 10px; border-radius: 5px 5px 0 0; margin-bottom: 20px; }
                .email-subject { font-weight: bold; }
                .email-body { padding: 10px 0; }
                .email-footer { margin-top: 20px; font-size: 12px; color: #777; border-top: 1px solid #ddd; padding-top: 10px; }
            </style>
        </head>
        <body>
            <div class="email-container">
                <div class="email-header">
                    <div class="email-subject">Sujet: ${subject}</div>
                    <div>À: ${testData.prenom} ${testData.nom} &lt;${testData.email}&gt;</div>
                    <div>De: Bioforce &lt;contact@bioforce.org&gt;</div>
                    <div>Date: ${testData.date}</div>
                </div>
                <div class="email-body">
                    ${previewContent}
                </div>
                <div class="email-footer">
                    <p>Ceci est une prévisualisation avec des données de test.</p>
                    <p> 2023 Bioforce - Tous droits réservés.</p>
                </div>
            </div>
        </body>
        </html>
    `);
    previewWindow.document.close();
}

const API_ENDPOINTS = {
    systemInfo: '/api/admin/system-info',
    qdrantStats: '/api/admin/qdrant-stats',
    gitUpdate: '/api/admin/git-update',
    scrapeFaq: '/api/scrape/faq',
    scrapeFull: '/api/scrape/full',
    logs: '/api/admin/logs',
    status: '/api/admin/status',
    emailTemplate: '/api/admin/email-template'
};