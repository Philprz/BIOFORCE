// SOLUTION D'URGENCE - CHATBOT BIOFORCE
// Version autonome ne nécessitant aucun serveur
// Fonctionne directement dans le navigateur sans connexion

// Configuration
const ADMIN_PASSWORD = "bioforce2025"; // Mot de passe pour l'accès admin

// Base de connaissances intégrée (simulation de la base Qdrant)
const KNOWLEDGE_BASE = [
    {
        question: "Quelles formations propose Bioforce ?",
        answer: "Bioforce propose plusieurs formations dans le domaine humanitaire, notamment :\n\n**Formations métiers** :\n- Responsable logistique humanitaire\n- Coordinateur·rice de projet humanitaire\n- Responsable RH & Finances humanitaire\n- Responsable de projets Eau, Hygiène et Assainissement\n\n**Formations courtes et certifiantes** :\n- Gestion financière de projets humanitaires\n- Gestion de la logistique humanitaire\n- Gestion des RH dans les ONG\n- Coordination de projets humanitaires",
        url: "https://www.bioforce.org/learn/formations-humanitaires/"
    },
    {
        question: "Comment financer ma formation ?",
        answer: "Plusieurs options de financement sont disponibles pour nos formations :\n\n**Financement personnel** :\n- Paiement en plusieurs fois sans frais\n- Possibilité de bourses Bioforce (sur critères sociaux)\n\n**Financement externe** :\n- Compte Personnel de Formation (CPF)\n- Pôle Emploi (AIF, POEI)\n- Employeur (plan de développement des compétences)\n- Organismes publics (régions, départements)\n- Prêt étudiant",
        url: "https://www.bioforce.org/learn/financer-ma-formation/"
    },
    {
        question: "Comment s'inscrire à une formation ?",
        answer: "Le processus d'inscription aux formations Bioforce comprend plusieurs étapes :\n\n1. **Dépôt du dossier de candidature** (en ligne)\n2. **Étude de votre candidature** par la commission d'admission\n3. **Entretien de sélection** (pour évaluer votre parcours et votre projet)\n4. **Résultat d'admission** communiqué environ 2 semaines après l'entretien\n5. **Inscription définitive** (avec paiement des frais d'inscription)\n\nLes dates de rentrée dépendent de la formation choisie, consultez notre site pour les calendriers détaillés.",
        url: "https://www.bioforce.org/learn/candidater/"
    },
    {
        question: "Quels sont les débouchés après une formation Bioforce ?",
        answer: "Les débouchés après une formation Bioforce sont nombreux dans le secteur humanitaire :\n\n**Types d'organisations** :\n- ONG internationales et nationales\n- Agences des Nations Unies\n- Croix-Rouge et Croissant-Rouge\n- Organisations internationales\n- Fondations et institutions publiques\n\n**Taux d'insertion professionnelle** :\n- Plus de 80% de nos diplômés trouvent un emploi dans les 6 mois\n- 93% sont en poste dans l'année suivant leur diplomation\n\nNos formations sont reconnues par les acteurs du secteur, ce qui facilite l'accès à l'emploi dans l'humanitaire.",
        url: "https://www.bioforce.org/learn/apres-bioforce/"
    },
    {
        question: "Quelles sont les conditions d'admission ?",
        answer: "Les conditions d'admission aux formations Bioforce varient selon le programme choisi :\n\n**Formations certifiantes** :\n- Niveau bac+2 minimum recommandé\n- Expérience préalable appréciée mais non obligatoire\n- Bonne maîtrise du français (et de l'anglais pour certaines formations)\n\n**Formations diplômantes** :\n- Bac+2 minimum requis (ou équivalent)\n- Expérience professionnelle ou bénévole valorisée\n- Niveau B2 en français et niveau B1/B2 en anglais\n\nNous évaluons chaque candidature dans sa globalité, en tenant compte de votre parcours, de votre motivation et de votre projet professionnel.",
        url: "https://www.bioforce.org/learn/candidater/conditions-dadmission/"
    },
    {
        question: "Où se déroulent les formations ?",
        answer: "Les formations Bioforce se déroulent sur différents sites :\n\n**En France** :\n- Centre de formation de Vénissieux (région lyonnaise)\n- Possibilité de formations à distance pour certains modules\n\n**À l'international** :\n- Centre régional de Dakar (Sénégal)\n- Centre de formation à Amman (Jordanie)\n- Programmes délocalisés en Centrafrique et RDC\n\nCertaines formations combinent des phases présentielles et des phases à distance (format hybride).",
        url: "https://www.bioforce.org/qui-sommes-nous/nos-centres/"
    },
    {
        question: "Quelle est la durée des formations ?",
        answer: "La durée des formations Bioforce varie selon le programme choisi :\n\n**Formations métiers** :\n- Format long : 9 à 12 mois (incluant stage pratique)\n- Format court : 3 à 6 mois (pour les personnes déjà expérimentées)\n\n**Formations courtes** :\n- Modules spécifiques : 1 à 3 semaines\n- Certificats de compétences : 2 à 3 mois\n\nNous proposons différents rythmes adaptés aux profils des apprenants, notamment des parcours complets, des parcours partiels et des formats hybrides combinant présentiel et distanciel.",
        url: "https://www.bioforce.org/learn/formations-humanitaires/"
    },
    {
        question: "Quel est le coût des formations ?",
        answer: "Le coût des formations Bioforce varie selon les programmes :\n\n**Formations métiers (parcours complet)** :\n- Entre 5000€ et 9000€ selon la formation\n- Tarif solidaire disponible (sous conditions)\n\n**Formations courtes** :\n- Modules spécifiques : entre 500€ et 1500€\n- Certificats de compétences : entre 1500€ et 3000€\n\nDes frais de sélection (non remboursables) sont à prévoir lors de la candidature. De nombreuses solutions de financement sont disponibles pour vous aider à couvrir ces frais.",
        url: "https://www.bioforce.org/learn/financer-ma-formation/financements-disponibles/"
    },
    {
        question: "Est-ce que Bioforce aide à trouver un stage ou un emploi ?",
        answer: "Oui, Bioforce propose plusieurs services pour faciliter votre insertion professionnelle :\n\n**Pendant la formation** :\n- Accompagnement personnalisé pour la recherche de stage\n- Réseaux de partenaires ONG et organisations internationales\n- Ateliers de techniques de recherche d'emploi\n\n**Après la formation** :\n- Accès à notre plateforme d'offres d'emploi\n- Réseau Alumni Bioforce (plus de 3000 professionnels)\n- Événements de networking avec des employeurs\n\nNos partenariats avec les acteurs majeurs du secteur humanitaire facilitent l'accès aux opportunités professionnelles pour nos diplômés.",
        url: "https://www.bioforce.org/learn/apres-bioforce/"
    },
    {
        question: "Quelle est la reconnaissance des diplômes Bioforce ?",
        answer: "Les formations Bioforce bénéficient de plusieurs reconnaissances :\n\n**Reconnaissances officielles** :\n- Certifications professionnelles enregistrées au RNCP (niveaux 6 et 7)\n- Reconnaissance de l'État français\n- Accréditation par des organismes internationaux\n\n**Reconnaissance sectorielle** :\n- Formations co-construites avec les acteurs humanitaires\n- Partenariats avec les principales ONG et organisations internationales\n- Forte notoriété dans le secteur humanitaire\n\nNos diplômes sont également reconnus à l'international grâce à nos partenariats avec des universités étrangères et des organismes internationaux.",
        url: "https://www.bioforce.org/qui-sommes-nous/notre-pedagogie/"
    },
    {
        question: "Peut-on suivre une formation à distance ?",
        answer: "Oui, Bioforce propose des options de formation à distance :\n\n**Formations hybrides** :\n- Alternance entre modules à distance et sessions présentielles\n- Plateforme d'apprentissage en ligne\n\n**Formations 100% à distance** :\n- Certains modules spécifiques\n- Certains certificats de compétences\n\nNotre approche pédagogique pour les formations à distance comprend :\n- Des sessions en direct avec les formateurs\n- Des travaux pratiques et études de cas\n- Des rendez-vous individuels de suivi\n- Une communauté d'apprenants en ligne\n\nCertains aspects pratiques nécessitent toutefois des sessions en présentiel, notamment pour les formations métiers complètes.",
        url: "https://www.bioforce.org/learn/formations-humanitaires/"
    },
    {
        question: "Quelles sont les dates de candidature ?",
        answer: "Les périodes de candidature chez Bioforce fonctionnent comme suit :\n\n**Pour les formations métiers** :\n- Plusieurs sessions de candidature par an\n- Dates limites généralement 3-4 mois avant le début de la formation\n\n**Pour les formations courtes** :\n- Candidatures possibles tout au long de l'année\n- Clôture généralement 1 mois avant le début\n\nConsultez notre site internet pour le calendrier exact des prochaines sessions. Il est recommandé de candidater le plus tôt possible car les places sont limitées et attribuées au fur et à mesure des admissions.",
        url: "https://www.bioforce.org/learn/candidater/calendrier/"
    },
    {
        question: "Comment se déroule la formation ?",
        answer: "Les formations Bioforce suivent une pédagogie spécifique :\n\n**Approche pédagogique** :\n- Apprentissage par l'action (70% de pratique)\n- Cas réels et mises en situation professionnelle\n- Travaux de groupe et projets collaboratifs\n\n**Organisation des cours** :\n- Modules thématiques progressifs\n- Formateurs professionnels du secteur humanitaire\n- Applications terrain et simulations de mission\n\n**Évaluation** :\n- Contrôle continu sur les travaux pratiques\n- Évaluations à la fin de chaque module\n- Projet professionnel de fin de formation\n- Stage pratique en situation réelle\n\nNous privilégions une approche par compétences, directement applicable sur le terrain humanitaire.",
        url: "https://www.bioforce.org/qui-sommes-nous/notre-pedagogie/"
    }
];

// Mots-clés associés aux questions de candidature/admission
const FORMATION_KEYWORDS = [
    "formation", "étudier", "apprendre", "cours", "programme", 
    "devenir", "métier", "carrière", "humanitaire", "diplôme"
];

const ORIENTATION_KEYWORDS = [
    "orientation", "test", "choix", "carrière", "métier", "convient", 
    "profil", "compétence", "aptitude"
];

// Éléments DOM
const chatWidget = document.getElementById('chatbot-widget');
const chatHeader = document.querySelector('.chat-header');
const chatMessages = document.getElementById('chat-messages');
const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-message');
const minimizeButton = document.getElementById('minimize-chat');
const adminButton = document.getElementById('admin-btn');

// Éléments de la boîte de dialogue admin
const adminOverlay = document.getElementById('admin-overlay');
const adminDialog = document.getElementById('admin-dialog');
const adminPassword = document.getElementById('admin-password');
const cancelAdminBtn = document.getElementById('cancel-admin');
const loginAdminBtn = document.getElementById('login-admin');

// Variables globales
let isDragging = false;
let dragOffsetX, dragOffsetY;
let chatHistory = [];
let userId = 'demo-user-' + Math.floor(Math.random() * 1000);

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
    formattedMessage = formattedMessage.replace(/\n/g, '<br>');
    
    messageDiv.innerHTML = `<p>${formattedMessage}</p>`;
    chatMessages.appendChild(messageDiv);
    
    // Faire défiler vers le bas pour voir le nouveau message
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    // Enregistrer le message dans l'historique
    if (sender === 'user') {
        chatHistory.push({
            role: 'user',
            content: message
        });
    } else if (sender === 'bot') {
        chatHistory.push({
            role: 'assistant',
            content: message
        });
    }
}

// Fonction pour obtenir une réponse du chatbot (version autonome)
function getResponseForQuery(userMessage) {
    const messageLower = userMessage.toLowerCase();
    
    // Recherche par similarité avec les questions existantes
    let bestMatch = null;
    let highestScore = 0;
    
    for (const entry of KNOWLEDGE_BASE) {
        const questionLower = entry.question.toLowerCase();
        
        // Calcul simple de similarité: compter le nombre de mots correspondants
        const words = messageLower.split(/\s+/);
        let score = 0;
        
        for (const word of words) {
            if (word.length > 3 && questionLower.includes(word)) {
                score += 1;
            }
        }
        
        // Bonus pour les correspondances exactes de phrases
        if (questionLower.includes(messageLower) || messageLower.includes(questionLower)) {
            score += 3;
        }
        
        if (score > highestScore) {
            highestScore = score;
            bestMatch = entry;
        }
    }
    
    // Si le score est trop bas, donner une réponse générique
    if (highestScore < 2) {
        return {
            content: "Je n'ai pas trouvé d'information précise sur ce sujet dans ma base de connaissances. N'hésitez pas à reformuler votre question ou à contacter directement notre équipe pour plus d'informations.",
            source: "https://www.bioforce.org/contact/"
        };
    }
    
    return bestMatch;
}

// Fonction pour détecter si le message concerne les formations
function isFormationRelated(message) {
    const messageLower = message.toLowerCase();
    return FORMATION_KEYWORDS.some(keyword => messageLower.includes(keyword));
}

// Fonction pour détecter si le message concerne l'orientation
function isOrientationRelated(message) {
    const messageLower = message.toLowerCase();
    return ORIENTATION_KEYWORDS.some(keyword => messageLower.includes(keyword));
}

// Fonction pour gérer l'envoi d'un message
function handleSendMessage() {
    const message = userInput.value.trim();
    
    if (message === '') return;
    
    // Ajouter le message de l'utilisateur
    addMessageToChat(message, 'user');
    
    // Vider l'input
    userInput.value = '';
    
    // Ajouter indication de chargement
    const loadingDiv = document.createElement('div');
    loadingDiv.classList.add('message', 'bot', 'loading');
    loadingDiv.innerHTML = '<p>...</p>';
    chatMessages.appendChild(loadingDiv);
    
    // Simuler un délai de traitement
    setTimeout(() => {
        // Supprimer l'indication de chargement
        chatMessages.removeChild(loadingDiv);
        
        // Obtenir la réponse
        const response = getResponseForQuery(message);
        
        // Ajouter la réponse du chatbot
        addMessageToChat(response.content, 'bot');
        
        // Ajouter un lien vers la source
        if (response.url) {
            const sourceDiv = document.createElement('div');
            sourceDiv.classList.add('message', 'bot', 'sources');
            sourceDiv.innerHTML = `
                <p><small>Pour plus d'informations, consultez :</small></p>
                <p><a href="${response.url}" target="_blank" class="source-link">
                    ${response.url.replace('https://www.bioforce.org/', '')} →
                </a></p>
            `;
            chatMessages.appendChild(sourceDiv);
        }
        
        // Vérifier si le message concerne les formations ou l'orientation
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
    }, 1000);
}

// Fonction pour afficher la boîte de dialogue admin
function showAdminDialog() {
    adminOverlay.style.display = 'block';
    adminDialog.style.display = 'block';
    adminPassword.value = ''; // Réinitialiser le champ de mot de passe
    adminPassword.focus();
}

// Fonction pour cacher la boîte de dialogue admin
function hideAdminDialog() {
    adminOverlay.style.display = 'none';
    adminDialog.style.display = 'none';
}

// Fonction pour vérifier le mot de passe admin
function checkAdminPassword() {
    const password = adminPassword.value;
    
    if (password === ADMIN_PASSWORD) {
        hideAdminDialog();
        
        // Rediriger vers la page d'administration
        window.location.href = "admin.html";
    } else {
        alert("Mot de passe incorrect. Veuillez réessayer.");
        adminPassword.value = '';
        adminPassword.focus();
    }
}

// Écouteurs d'événements
sendButton.addEventListener('click', handleSendMessage);
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        handleSendMessage();
    }
});

minimizeButton.addEventListener('click', () => {
    chatWidget.classList.toggle('minimized');
    minimizeButton.textContent = chatWidget.classList.contains('minimized') ? '+' : '−';
});

// Écouteurs d'événements pour l'administration
adminButton.addEventListener('click', showAdminDialog);
cancelAdminBtn.addEventListener('click', hideAdminDialog);
loginAdminBtn.addEventListener('click', checkAdminPassword);

// Message d'accueil du chatbot
window.addEventListener('DOMContentLoaded', function() {
    if (chatMessages.children.length === 0) {
        addMessageToChat("Bonjour ! Je suis le chatbot Bioforce. Comment puis-je vous aider aujourd'hui ?", 'bot');
    }
});
