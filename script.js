// ==================== API base (Flask on localhost) ====================
function apiOrigin() {
    return window.location.origin === 'file://' ? 'http://localhost:5000' : '';
}

// ==================== DOM Elements ====================
const welcomePage = document.getElementById('welcome-page');
const questionPage = document.getElementById('question-page');
const startBtn = document.getElementById('start-btn');
const backBtn = document.getElementById('back-btn');
const submitBtn = document.getElementById('submit-btn');
const questionInput = document.getElementById('question-input');
const answerContainer = document.getElementById('answer-container');
const answerText = document.getElementById('answer-text');
const providerBadge = document.getElementById('provider-badge');
const loading = document.getElementById('loading');

// New feature elements
const voiceBtn = document.getElementById('voice-btn');
const speakBtn = document.getElementById('speak-btn');
const voiceAssistantBtn = document.getElementById('voice-assistant-btn');
const vaStatusBar = document.getElementById('va-status-bar');
const vaStatusText = document.getElementById('va-status-text');
const copyBtn = document.getElementById('copy-btn');
const historyBtn = document.getElementById('history-btn');
const historyModal = document.getElementById('history-modal');
const historyList = document.getElementById('history-list');
const historyFilterInput = document.getElementById('history-filter-input');
const closeModal = document.getElementById('close-modal');
const clearHistory = document.getElementById('clear-history');
const historyClearFilter = document.getElementById('history-clear-filter');
const datasetSelect = document.getElementById('dataset-select');
const providerStatus = document.getElementById('provider-status');
const feedbackInput = document.getElementById('feedback-input');
const feedbackSubmit = document.getElementById('feedback-submit');
const quickBtns = document.querySelectorAll('.quick-btn');
const toast = document.getElementById('toast');
const toastMessage = document.getElementById('toast-message');

const btnLocation = document.getElementById('btn-location');
const btnLocationSidebar = document.getElementById('btn-location-sidebar');
const btnCamera = document.getElementById('btn-camera');
const btnCameraSidebar = document.getElementById('btn-camera-sidebar');
const btnProfile = document.getElementById('btn-profile');
const homeBtn = document.getElementById('home-btn');
const btnProfileSidebar = document.getElementById('btn-profile-sidebar');
const btnDashboard = document.getElementById('btn-dashboard');
const btnDashboardSidebar = document.getElementById('btn-dashboard-sidebar');
const aboutBtn = document.getElementById('about-btn');
const aboutBtnSidebar = document.getElementById('about-btn-sidebar');
const newChatBtn = document.getElementById('new-chat');
const langSelect = document.getElementById('lang-select');
const weatherPanel = document.getElementById('weather-panel');
const weatherLine = document.getElementById('weather-line');
const alertsList = document.getElementById('alerts-list');
const profileModal = document.getElementById('profile-modal');
const closeProfile = document.getElementById('close-profile');
const saveProfile = document.getElementById('save-profile');
const cropImageInput = document.getElementById('crop-image-input');
const cropImageCamera = document.getElementById('crop-image-camera');
const imagePreview = document.getElementById('image-preview');
const clearImageBtn = document.getElementById('clear-image');
const photoPreviewCard = document.getElementById('photo-preview-card');
const photoOptions = document.getElementById('photo-options');
const btnGallery = document.getElementById('btn-gallery');

const aboutModal = document.getElementById('about-modal');
const closeAbout = document.getElementById('close-about');
const dashboardModal = document.getElementById('dashboard-modal');
const closeDashboard = document.getElementById('close-dashboard');
const refreshDashboard = document.getElementById('refresh-dashboard');
const dashAlerts = document.getElementById('dash-alerts');
const dashTips = document.getElementById('dash-tips');
const dashMarket = document.getElementById('dash-market');

// Music elements
const bgMusic = document.getElementById('bg-music');
const musicToggle = document.getElementById('music-toggle');
const musicIcon = musicToggle.querySelector('.music-icon');
const musicText = musicToggle.querySelector('.music-text');

// ==================== State ====================
let isMusicPlaying = false;
let isListening = false;
let isSpeaking = false;
let voiceAssistantMode = false;
let recognition = null;
let synthesis = window.speechSynthesis;
let questionHistory = JSON.parse(localStorage.getItem('farmingHistory') || '[]');

let farmLat = null;
let farmLon = null;
let pendingImageBase64 = null;
let pendingImageMime = 'image/jpeg';

const LS_PROFILE = 'farmProfileV1';
const LS_LANG = 'langPreferenceV1';

const developerAnswer = `Ayushmaan Singh Pundir is an aspiring developer with a growing interest in technology and software development. He is currently building foundational skills in programming, problem-solving, and logical thinking, and is enthusiastic about learning modern development tools and practices. Ayushmaan demonstrates curiosity, discipline, and a willingness to explore new concepts, which are essential qualities for a successful developer.

He is focused on strengthening his understanding of core subjects such as programming fundamentals, mathematics, and computational thinking. With continued guidance and hands-on practice, Ayushmaan is expected to develop strong technical capabilities and contribute effectively to future software development projects.`;

function isDeveloperQuery(text) {
    if (!text) return false;
    const q = text.toLowerCase();
    return [
        'who is your developer',
        'who developed you',
        'who built you',
        'who made you',
        'developer',
        'created you',
        'developed by',
        'ayushmaan',
        'deepseek',
        'deepmind'
    ].some((kw) => q.includes(kw));
}

// ==================== Music Controls ====================
let audioReady = false;

if (bgMusic) {
    bgMusic.volume = 0.5;
    
    // Preload the audio
    bgMusic.load();
    
    // Track when audio is ready
    bgMusic.addEventListener('canplaythrough', () => {
        audioReady = true;
        console.log('Audio ready to play');
    });
    
    bgMusic.addEventListener('error', (e) => {
        console.error('Audio error:', e);
        audioReady = false;
    });
}

function updateMusicButton(playing) {
    if (playing) {
        musicIcon.textContent = '🎵';
        musicText.textContent = 'Music On';
        musicToggle.classList.add('playing');
    } else {
        musicIcon.textContent = '🔇';
        musicText.textContent = 'Music Off';
        musicToggle.classList.remove('playing');
    }
}

// Music toggle click handler
musicToggle.addEventListener('click', function(e) {
    e.preventDefault();
    e.stopPropagation();
    
    console.log('Music button clicked, current state:', isMusicPlaying);
    
    if (!bgMusic) {
        console.error('Audio element not found');
        return;
    }
    
    if (isMusicPlaying) {
        // Pause music
        bgMusic.pause();
        isMusicPlaying = false;
        // Update button immediately
        musicIcon.textContent = '🔇';
        musicText.textContent = 'Music Off';
        musicToggle.classList.remove('playing');
        console.log('Music paused');
    } else {
        // Play music - update UI first for responsiveness
        musicIcon.textContent = '🎵';
        musicText.textContent = 'Music On';
        musicToggle.classList.add('playing');
        
        console.log('Attempting to play music...');
        
        bgMusic.play()
            .then(() => {
                isMusicPlaying = true;
                console.log('Music playing successfully!');
            })
            .catch((error) => {
                console.error('Play failed:', error);
                isMusicPlaying = false;
                // Revert button state on error
                musicIcon.textContent = '🔇';
                musicText.textContent = 'Music Off';
                musicToggle.classList.remove('playing');
            });
    }
});

// ==================== Voice Assistant Mode ====================
function setVoiceAssistantMode(enabled) {
    voiceAssistantMode = enabled;
    if (enabled) {
        voiceAssistantBtn.classList.add('active');
        vaStatusBar.classList.remove('hidden');
        vaStatusText.textContent = 'Voice Assistant Active — tap 🎤 to speak, answer will be read aloud';
        showToast('🎙️ Voice Assistant ON — speak your question!');
    } else {
        voiceAssistantBtn.classList.remove('active');
        vaStatusBar.classList.add('hidden');
        stopSpeaking();
        showToast('Voice Assistant OFF');
    }
}

if (voiceAssistantBtn) {
    voiceAssistantBtn.addEventListener('click', () => {
        setVoiceAssistantMode(!voiceAssistantMode);
    });
}

// ==================== Dashboard ====================
async function loadDashboard() {
    // Weather alerts
    if (dashAlerts) {
        const alertItems = document.querySelectorAll('#alerts-list li');
        if (alertItems.length > 0) {
            dashAlerts.innerHTML = Array.from(alertItems).map(li => {
                const text = li.textContent;
                const isOk = text.toLowerCase().includes('no immediate');
                return `<div class="dash-alert-item ${isOk ? 'dash-alert-ok' : ''}">${isOk ? '✅' : '⚠️'} ${text}</div>`;
            }).join('');
        } else {
            dashAlerts.innerHTML = '<p class="dash-empty">Tap "📍 Get Weather" on the main screen to see weather alerts.</p>';
        }
    }

    // Proactive tips from /insights
    if (dashTips) {
        try {
            const profile = JSON.parse(localStorage.getItem('farmProfileV1') || '{}');
            const crop = (profile.crop || '').trim();
            const district = (profile.district || '').trim();
            let url = `${apiOrigin()}/insights?`;
            if (crop) url += `crop=${encodeURIComponent(crop)}&`;
            if (district) url += `district=${encodeURIComponent(district)}&`;
            if (farmLat != null) url += `lat=${farmLat}&lon=${farmLon}`;
            const r = await fetch(url);
            const d = await r.json();
            if (d.proactive_tips && d.proactive_tips.length) {
                dashTips.innerHTML = d.proactive_tips.map(t =>
                    `<div class="dash-tip-item">💡 ${t}</div>`
                ).join('');
            } else {
                dashTips.innerHTML = '<p class="dash-empty">Set your crop in "👤 My Farm" to see personalised tips.</p>';
            }
            // Also update market from insights
            if (d.market_snapshot && dashMarket) {
                renderMarket(d.market_snapshot);
            }
        } catch (e) {
            dashTips.innerHTML = '<p class="dash-empty">Could not load tips — make sure the server is running.</p>';
        }
    }
}

function renderMarket(marketData) {
    if (!dashMarket) return;
    const crops = marketData.crops || [];
    if (!crops.length) { dashMarket.innerHTML = '<p class="dash-empty">No market data.</p>'; return; }
    dashMarket.innerHTML = crops.map(c => {
        const trend = (c.trend || '').toLowerCase();
        const trendClass = trend.includes('up') ? 'trend-up' : trend.includes('down') ? 'trend-down' : 'trend-stable';
        const trendIcon = trend.includes('up') ? '↑' : trend.includes('down') ? '↓' : '→';
        return `
        <div class="market-card">
            <div class="crop-name">${c.name}</div>
            <div class="crop-price">₹${c.price}</div>
            <div class="crop-unit">${marketData.unit || 'per quintal'}</div>
            <span class="crop-trend ${trendClass}">${trendIcon} ${c.trend}</span>
            <div class="crop-tip">${c.tip}</div>
        </div>`;
    }).join('');
}

if (aboutBtn) aboutBtn.addEventListener('click', () => aboutModal && aboutModal.classList.remove('hidden'));
if (closeAbout) closeAbout.addEventListener('click', () => aboutModal && aboutModal.classList.add('hidden'));
if (aboutModal) aboutModal.addEventListener('click', (e) => { if (e.target === aboutModal) aboutModal.classList.add('hidden'); });

if (btnDashboard) {
    btnDashboard.addEventListener('click', async () => {
        if (dashboardModal) {
            dashboardModal.classList.remove('hidden');
            await loadDashboard();
        }
    });
}

if (closeDashboard) {
    closeDashboard.addEventListener('click', () => dashboardModal.classList.add('hidden'));
}

if (dashboardModal) {
    dashboardModal.addEventListener('click', (e) => {
        if (e.target === dashboardModal) dashboardModal.classList.add('hidden');
    });
}

if (refreshDashboard) {
    refreshDashboard.addEventListener('click', async () => {
        showToast('🔄 Refreshing dashboard…');
        await loadDashboard();
    });
}

// Sidebar quick action mapping
if (btnLocationSidebar && btnLocation) {
    btnLocationSidebar.addEventListener('click', () => btnLocation.click());
}
if (btnCameraSidebar && btnCamera) {
    btnCameraSidebar.addEventListener('click', () => btnCamera.click());
}
if (btnProfileSidebar && btnProfile) {
    btnProfileSidebar.addEventListener('click', () => btnProfile.click());
}
if (btnDashboardSidebar && btnDashboard) {
    btnDashboardSidebar.addEventListener('click', () => btnDashboard.click());
}
if (aboutBtnSidebar && aboutBtn) {
    aboutBtnSidebar.addEventListener('click', () => aboutBtn.click());
}
if (homeBtn) {
    homeBtn.addEventListener('click', () => {
        welcomePage.classList.add('active');
        questionPage.classList.remove('active');
        document.querySelectorAll('.sidebar-btn').forEach(b => b.classList.remove('active'));
        homeBtn.classList.add('active');
    });
}

if (newChatBtn) {
    newChatBtn.addEventListener('click', () => {
        questionInput.value = '';
        answerContainer.classList.add('hidden');
        clearPhoto();
        if (voiceAssistantMode) setVoiceAssistantMode(false);
        document.querySelectorAll('.sidebar-btn').forEach(b => b.classList.remove('active'));
        newChatBtn.classList.add('active');
    });
}

const modePills = document.querySelectorAll('.mode-pill');
modePills.forEach((pill) => {
    pill.addEventListener('click', () => {
        modePills.forEach((p) => p.classList.remove('active'));
        pill.classList.add('active');
        const mode = pill.dataset.mode;
        if (mode === 'market') {
            showToast('📈 Market mode selected (context switch)');
        } else if (mode === 'diagnosis') {
            showToast('🔬 Diagnosis mode selected (use camera for crop health)');
        } else {
            showToast('🌱 Farming mode selected');
        }
    });
});

// ==================== Page Navigation ====================
startBtn.addEventListener('click', () => {
    welcomePage.classList.remove('active');
    questionPage.classList.add('active');
    questionInput.focus();
    document.querySelectorAll('.sidebar-btn').forEach(b => b.classList.remove('active'));
    if (newChatBtn) newChatBtn.classList.add('active');
});

backBtn.addEventListener('click', () => {
    questionPage.classList.remove('active');
    welcomePage.classList.add('active');
    questionInput.value = '';
    answerContainer.classList.add('hidden');
    clearPhoto();
    stopSpeaking();
    if (voiceAssistantMode) setVoiceAssistantMode(false);
});

// ==================== Voice Input (Speech-to-Text) ====================
function speechRecognitionLang() {
    if (langSelect && langSelect.value) return langSelect.value;
    const lang = navigator.language || navigator.userLanguage || 'en-US';
    return /^en/i.test(lang) ? lang : 'en-US';
}

function initVoiceRecognition() {
    if (!voiceBtn || !questionInput) return;
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        voiceBtn.disabled = true;
        voiceBtn.title = 'Voice input requires Chrome or Edge (Web Speech API)';
        return;
    }

    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognition.lang = speechRecognitionLang();

    recognition.onstart = () => {
        isListening = true;
        voiceBtn.classList.add('listening');
        if (voiceAssistantMode) {
            vaStatusText.textContent = '🎤 Listening… speak your question';
        } else {
            showToast('Listening… speak your question.');
        }
    };

    recognition.onresult = (event) => {
        let transcript = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
            transcript += event.results[i][0].transcript;
        }
        const t = transcript.trim();
        if (t) {
            const prefix = questionInput.value.trim();
            questionInput.value = prefix ? `${prefix} ${t}` : t;
            questionInput.focus();
            // In voice assistant mode, auto-submit after speech is captured
            if (voiceAssistantMode) {
                vaStatusText.textContent = 'Processing your question…';
                setTimeout(() => submitBtn.click(), 300);
            }
        }
    };

    recognition.onend = () => {
        isListening = false;
        voiceBtn.classList.remove('listening');
        if (voiceAssistantMode && !isSpeaking) {
            vaStatusText.textContent = 'Voice Assistant Active — tap 🎤 to speak';
        }
    };

    recognition.onerror = (event) => {
        isListening = false;
        voiceBtn.classList.remove('listening');
        const err = event.error;
        console.warn('Speech recognition:', err);
        if (err === 'not-allowed' || err === 'service-not-allowed') {
            showToast('Allow microphone access for voice input (browser site settings).');
        } else if (err === 'no-speech') {
            showToast('No speech heard. Try again or speak closer to the mic.');
        } else if (err === 'aborted') {
            /* user stopped or page hid */
        } else if (err === 'network') {
            showToast('Voice recognition needs a network connection in this browser.');
        } else {
            showToast('Voice input failed. Try again or type your question.');
        }
    };
}

function startRecognition() {
    if (!recognition) return;
    try {
        recognition.start();
    } catch (e) {
        if (e.name === 'InvalidStateError') {
            try {
                recognition.stop();
            } catch (e2) { /* ignore */ }
            setTimeout(() => {
                try {
                    recognition.start();
                } catch (e3) {
                    showToast('Voice is busy. Wait a second and tap again.');
                }
            }, 150);
        } else {
            showToast('Could not start voice input.');
        }
    }
}

if (voiceBtn) {
    voiceBtn.addEventListener('click', () => {
        if (!recognition) initVoiceRecognition();
        if (!recognition) {
            showToast('Voice input is not supported in this browser. Use Chrome or Edge.');
            return;
        }

        if (isListening) {
            try {
                recognition.stop();
            } catch (e) { /* ignore */ }
            return;
        }

        startRecognition();
    });
}

// ==================== Text-to-Speech ====================
function pickVoiceForLanguage(langCode) {
    const voices = synthesis.getVoices();
    if (!voices.length) return null;
    const code = (langCode || 'en-US').toLowerCase();
    const base = code.split('-')[0];
    return (
        voices.find((v) => (v.lang || '').toLowerCase() === code) ||
        voices.find((v) => (v.lang || '').toLowerCase().startsWith(code)) ||
        voices.find((v) => (v.lang || '').toLowerCase().startsWith(base)) ||
        voices.find((v) => (v.lang || '').toLowerCase().includes('en-us')) ||
        voices.find((v) => (v.lang || '').toLowerCase().includes('en')) ||
        voices[0]
    );
}

function speak(text) {
    if (!synthesis) {
        showToast('⚠️ Text-to-speech not supported');
        return;
    }

    synthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 0.9;
    utterance.pitch = 1;
    utterance.volume = 1.0;
    const langCode = langSelect ? langSelect.value : 'en-US';
    utterance.lang = langCode;

    // Wait for voices to be loaded before picking one
    const assignVoiceAndSpeak = () => {
        const v = pickVoiceForLanguage(langCode);
        if (v) utterance.voice = v;

        utterance.onstart = () => {
            isSpeaking = true;
            if (speakBtn) speakBtn.classList.add('active');
        };

        utterance.onend = () => {
            isSpeaking = false;
            if (speakBtn) speakBtn.classList.remove('active');
            if (voiceAssistantMode) {
                vaStatusText.textContent = 'Listening for your next question…';
                // Re-init to get a fresh recognition instance, then start
                setTimeout(() => {
                    if (voiceAssistantMode) {
                        initVoiceRecognition();
                        startRecognition();
                    }
                }, 600);
            }
        };

        utterance.onerror = (e) => {
            isSpeaking = false;
            if (speakBtn) speakBtn.classList.remove('active');
            console.warn('TTS error:', e.error);
        };

        // Chrome bugs: (1) speak() after cancel() silently fails without a delay;
        // (2) synthesis can silently pause — resume() ensures it is active.
        synthesis.resume();
        setTimeout(() => synthesis.speak(utterance), 200);
    };

    const voices = synthesis.getVoices();
    if (voices.length) {
        assignVoiceAndSpeak();
    } else {
        // Voices not loaded yet — wait for them
        synthesis.onvoiceschanged = () => {
            synthesis.onvoiceschanged = null;
            assignVoiceAndSpeak();
        };
    }
}

function stopSpeaking() {
    if (synthesis) {
        synthesis.cancel();
    }
    isSpeaking = false;
    if (speakBtn) speakBtn.classList.remove('active');
    // Stop ongoing recognition if running
    if (recognition && isListening) {
        try { recognition.stop(); } catch (e) { /* ignore */ }
    }
}

speakBtn.addEventListener('click', () => {
    if (isSpeaking) {
        stopSpeaking();
    } else {
        const text = answerText.textContent;
        if (text) {
            speak(text);
        }
    }
});

// ==================== Copy to Clipboard ====================
copyBtn.addEventListener('click', async () => {
    const text = answerText.textContent;
    if (text) {
        try {
            await navigator.clipboard.writeText(text);
            showToast('📋 Answer copied to clipboard!');
        } catch (err) {
            showToast('⚠️ Failed to copy');
        }
    }
});

// ==================== Quick Action Buttons ====================
quickBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        const question = btn.dataset.question;
        questionInput.value = question;
        submitBtn.click();
    });
});

// ==================== Question History ====================
function saveToHistory(question, answer) {
    const entry = {
        question,
        answer,
        timestamp: new Date().toISOString()
    };
    questionHistory.unshift(entry);
    if (questionHistory.length > 20) {
        questionHistory = questionHistory.slice(0, 20);
    }
    localStorage.setItem('farmingHistory', JSON.stringify(questionHistory));
    renderHistory();
}

function renderHistory() {
    const filter = historyFilterInput?.value.trim().toLowerCase() || '';
    const filteredHistory = filter
        ? questionHistory.filter((entry) =>
              entry.question.toLowerCase().includes(filter) ||
              (entry.answer && entry.answer.toLowerCase().includes(filter))
          )
        : questionHistory;

    if (filteredHistory.length === 0) {
        historyList.innerHTML = '<p class="empty-history">No matching history entries. Try a different filter.</p>';
        return;
    }

    historyList.innerHTML = filteredHistory.map((entry, index) => {
        const date = new Date(entry.timestamp);
        const timeStr = date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        return `
            <div class="history-item" data-index="${index}">
                <div class="history-question">${entry.question}</div>
                <div class="history-time">${timeStr}</div>
            </div>
        `;
    }).join('');

    // Add click handlers
    document.querySelectorAll('.history-item').forEach(item => {
        item.addEventListener('click', () => {
            const index = parseInt(item.dataset.index);
            const entry = filteredHistory[index];
            questionInput.value = entry.question;
            historyModal.classList.add('hidden');
            submitBtn.click();
        });
    });
}

historyBtn.addEventListener('click', () => {
    if (historyFilterInput) {
        historyFilterInput.value = '';
    }
    renderHistory();
    historyModal.classList.remove('hidden');
});

if (historyFilterInput) {
    historyFilterInput.addEventListener('input', () => {
        renderHistory();
    });
}

if (historyClearFilter) {
    historyClearFilter.addEventListener('click', () => {
        historyFilterInput.value = '';
        renderHistory();
        historyFilterInput.focus();
    });
}

closeModal.addEventListener('click', () => {
    historyModal.classList.add('hidden');
});

historyModal.addEventListener('click', (e) => {
    if (e.target === historyModal) {
        historyModal.classList.add('hidden');
    }
});

clearHistory.addEventListener('click', () => {
    questionHistory = [];
    localStorage.removeItem('farmingHistory');
    renderHistory();
    showToast('🗑️ History cleared');
});

// ==================== Toast Notification ====================
function showToast(message, duration = 3000) {
    toastMessage.textContent = message;
    toast.classList.add('show');
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, duration);
}

async function refreshProviderStatus() {
    if (!providerStatus) return;
    providerStatus.textContent = 'Provider status: checking…';
    try {
        const r = await fetch(`${apiOrigin()}/health`);
        const data = await r.json();
        const providers = (data.configured_providers || []).join(', ') || 'none';
        providerStatus.textContent = `Provider status: ${data.status || 'unknown'}; configured: ${providers}; total: ${data.total_providers || 0}`;
        providerStatus.classList.toggle('status-error', data.status !== 'ok');
    } catch (e) {
        providerStatus.textContent = 'Provider status: unavailable';
        providerStatus.classList.add('status-error');
    }
}

async function loadDatasets() {
    if (!datasetSelect) return;
    try {
        const r = await fetch(`${apiOrigin()}/datasets`);
        const data = await r.json();
        const datasets = data.datasets || [];
        datasetSelect.innerHTML = '<option value="all">All datasets (default)</option>' +
            datasets
                .filter((d) => d.id && d.id !== 'all')
                .map((d) => `<option value="${d.id}">${d.name || d.id}</option>`)
                .join('');
    } catch (e) {
        console.warn('Could not fetch datasets:', e);
    }
}

async function submitFeedback(question, answer) {
    if (!feedbackInput || !feedbackSubmit) return;
    const text = feedbackInput.value.trim();
    if (!text) {
        showToast('✍️ Enter feedback before sending');
        return;
    }
    feedbackSubmit.disabled = true;
    try {
        const r = await fetch(`${apiOrigin()}/feedback`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question, answer, feedback: text, timestamp: new Date().toISOString() }),
        });
        if (r.ok) {
            showToast('🙏 Feedback received. Thank you!');
            feedbackInput.value = '';
        } else {
            showToast('⚠️ Could not send feedback');
        }
    } catch (e) {
        showToast('⚠️ Feedback service unavailable');
        console.error('Feedback error', e);
    } finally {
        feedbackSubmit.disabled = false;
    }
}

// ==================== Farm profile & weather ====================
function collectFarmProfileFromForm() {
    const get = (id) => {
        const el = document.getElementById(id);
        return el ? el.value.trim() : '';
    };
    return {
        crop: get('profile-crop'),
        soil: get('profile-soil'),
        land_size: get('profile-land'),
        irrigation: get('profile-irrigation'),
        district: get('profile-district'),
    };
}

function loadFarmProfileIntoForm() {
    try {
        const p = JSON.parse(localStorage.getItem(LS_PROFILE) || '{}');
        const map = [
            ['profile-crop', 'crop'],
            ['profile-soil', 'soil'],
            ['profile-land', 'land_size'],
            ['profile-irrigation', 'irrigation'],
            ['profile-district', 'district'],
        ];
        map.forEach(([id, key]) => {
            const el = document.getElementById(id);
            if (el && p[key]) el.value = p[key];
        });
    } catch (e) {
        /* ignore */
    }
}

function escapeHtml(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

async function refreshWeather() {
    if (farmLat == null || farmLon == null || !weatherPanel) return;
    try {
        const r = await fetch(`${apiOrigin()}/weather?lat=${farmLat}&lon=${farmLon}`);
        const d = await r.json();
        if (d.error) throw new Error(d.error);
        weatherPanel.classList.remove('hidden');
        if (weatherLine) {
            const tr = d.tomorrow_precip_mm != null ? Number(d.tomorrow_precip_mm).toFixed(1) : '?';
            weatherLine.textContent = `About ${Math.round(d.temperature_c)}°C · humidity ${Math.round(d.humidity_pct)}% · tomorrow rain ~${tr} mm (forecast model)`;
        }
        if (alertsList && Array.isArray(d.alerts)) {
            alertsList.innerHTML = d.alerts.map((a) => `<li>${escapeHtml(a)}</li>`).join('');
        }
    } catch (e) {
        console.warn(e);
        showToast('Could not load weather.');
    }
}

if (btnLocation) {
    btnLocation.addEventListener('click', () => {
        if (!navigator.geolocation) {
            showToast('Location is not supported in this browser.');
            return;
        }
        showToast('Getting location…');
        navigator.geolocation.getCurrentPosition(
            async (pos) => {
                farmLat = pos.coords.latitude;
                farmLon = pos.coords.longitude;
                await refreshWeather();
                showToast('Location and weather updated.');
            },
            () => showToast('Location permission denied or unavailable.'),
            { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 }
        );
    });
}

if (btnProfile) btnProfile.addEventListener('click', () => profileModal.classList.remove('hidden'));
if (closeProfile) closeProfile.addEventListener('click', () => profileModal.classList.add('hidden'));
if (profileModal) {
    profileModal.addEventListener('click', (e) => {
        if (e.target === profileModal) profileModal.classList.add('hidden');
    });
}
if (saveProfile) {
    saveProfile.addEventListener('click', () => {
        const p = collectFarmProfileFromForm();
        localStorage.setItem(LS_PROFILE, JSON.stringify(p));
        profileModal.classList.add('hidden');
        showToast('Farm profile saved');
    });
}

// ── Photo upload helpers ──────────────────────────────────
function handleImageFile(file, sourceInput) {
    if (!file) return;
    if (file.size > 4 * 1024 * 1024) {
        showToast('⚠️ Image too large (max 4 MB). Please choose a smaller photo.');
        if (sourceInput) sourceInput.value = '';
        return;
    }
    const reader = new FileReader();
    reader.onload = () => {
        const dataUrl = reader.result;
        const m = /^data:([^;]+);base64,(.+)$/.exec(dataUrl);
        if (m) {
            pendingImageMime = m[1];
            pendingImageBase64 = m[2];
        }
        if (imagePreview) imagePreview.src = dataUrl;
        if (photoPreviewCard) photoPreviewCard.classList.remove('hidden');
        if (photoOptions) photoOptions.style.display = 'none';
        showToast('📸 Photo attached — ask your question!');
    };
    reader.readAsDataURL(file);
}

function clearPhoto() {
    pendingImageBase64 = null;
    pendingImageMime = 'image/jpeg';
    if (cropImageInput) cropImageInput.value = '';
    if (cropImageCamera) cropImageCamera.value = '';
    if (imagePreview) { imagePreview.src = ''; }
    if (photoPreviewCard) photoPreviewCard.classList.add('hidden');
    if (photoOptions) photoOptions.style.display = '';
}

if (btnGallery) btnGallery.addEventListener('click', () => cropImageInput && cropImageInput.click());
if (btnCamera)  btnCamera.addEventListener('click',  () => cropImageCamera && cropImageCamera.click());

if (cropImageInput) {
    cropImageInput.addEventListener('change', (e) => handleImageFile(e.target.files && e.target.files[0], cropImageInput));
}
if (cropImageCamera) {
    cropImageCamera.addEventListener('change', (e) => handleImageFile(e.target.files && e.target.files[0], cropImageCamera));
}
if (clearImageBtn) {
    clearImageBtn.addEventListener('click', clearPhoto);
}

if (langSelect) {
    langSelect.addEventListener('change', () => {
        localStorage.setItem(LS_LANG, langSelect.value);
        if (recognition) recognition.lang = langSelect.value;
    });
}

// ==================== Submit Question ====================
submitBtn.addEventListener('click', async () => {
    const question = questionInput.value.trim();
    
    if (!question) {
        showToast('⚠️ Please enter a question!');
        questionInput.focus();
        return;
    }

    if (isDeveloperQuery(question)) {
        answerText.textContent = developerAnswer;
        providerBadge.textContent = 'Powered by Crop Bot (local override)';
        answerContainer.classList.remove('hidden');
        showToast('✅ Developer info provided locally');
        saveToHistory(question, developerAnswer);
        if (voiceAssistantMode) speak(developerAnswer);
        return;
    }
    
    // Show loading, hide answer
    loading.classList.remove('hidden');
    answerContainer.classList.add('hidden');
    submitBtn.disabled = true;
    stopSpeaking();
    
    try {
        const apiUrl = `${apiOrigin()}/ask`;
        const payload = {
            question: question,
            dataset: datasetSelect && datasetSelect.value ? datasetSelect.value : 'all',
            farm_profile: collectFarmProfileFromForm(),
            language: langSelect ? langSelect.value : 'en-IN',
        };
        if (farmLat != null && farmLon != null) {
            payload.lat = farmLat;
            payload.lon = farmLon;
        }
        if (pendingImageBase64) {
            payload.image_base64 = pendingImageBase64;
            payload.image_mime = pendingImageMime;
        }

        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload)
        });
        
        const data = await response.json();
        
        if (response.status === 429 && data.error === 'quota_exceeded') {
            loading.classList.add('hidden');
            submitBtn.disabled = false;
            updateQuotaBar(0);
            showPaywall();
            return;
        }

        if (data.error) {
            answerText.innerHTML = `<span style="color: #ef4444;">❌ Error: ${data.error}</span>`;
            providerBadge.textContent = '';
        } else {
            if (data.queries_remaining != null) updateQuotaBar(data.queries_remaining);
            answerText.textContent = data.answer;
            let badge = data.provider ? `Powered by ${data.provider}` : '';
            if (data.image_analyzed) {
                badge = badge ? `${badge} · Photo analyzed` : 'Photo analyzed';
            }
            providerBadge.textContent = badge;
            
            // Save to history
            saveToHistory(question, data.answer);

            if (voiceAssistantMode) {
                // Auto-speak the answer and reset status for next question
                speak(data.answer);
                vaStatusText.textContent = 'Speaking answer… tap 🎤 again to ask another question';
            } else {
                showToast('✅ Answer ready!');
            }
        }
        
        answerContainer.classList.remove('hidden');
        
    } catch (error) {
        answerText.innerHTML = `<span style="color: #ef4444;">❌ Could not connect to server. Make sure the backend is running!</span>`;
        providerBadge.textContent = '';
        answerContainer.classList.remove('hidden');
        console.error('Error:', error);
    } finally {
        loading.classList.add('hidden');
        submitBtn.disabled = false;
    }
});

if (feedbackSubmit) {
    feedbackSubmit.addEventListener('click', () => {
        const last = questionHistory[0] || { question: '', answer: '' };
        submitFeedback(last.question, last.answer);
    });
}

// ==================== Keyboard Shortcuts ====================
questionInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        submitBtn.click();
    }
});

// Escape key to close modals
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        historyModal.classList.add('hidden');
        if (profileModal) profileModal.classList.add('hidden');
        if (dashboardModal) dashboardModal.classList.add('hidden');
        if (aboutModal) aboutModal.classList.add('hidden');
        if (calendarModal) calendarModal.classList.add('hidden');
        if (paywallModal) paywallModal.classList.add('hidden');
        stopSpeaking();
    }
});// ==================== Service Worker (PWA) ====================
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch((e) => console.warn('SW registration failed:', e));
}

// ==================== PWA Install Prompt ====================
let _deferredInstallPrompt = null;
const pwaBanner = document.getElementById('pwa-banner');
const pwaInstallBtn = document.getElementById('pwa-install-btn');
const pwaDismissBtn = document.getElementById('pwa-dismiss-btn');

window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    _deferredInstallPrompt = e;
    // Only show banner if user hasn't dismissed it before
    if (!localStorage.getItem('pwaBannerDismissed')) {
        setTimeout(() => pwaBanner && pwaBanner.classList.remove('hidden'), 4000);
    }
});

if (pwaInstallBtn) {
    pwaInstallBtn.addEventListener('click', async () => {
        if (!_deferredInstallPrompt) return;
        _deferredInstallPrompt.prompt();
        const { outcome } = await _deferredInstallPrompt.userChoice;
        _deferredInstallPrompt = null;
        pwaBanner.classList.add('hidden');
        if (outcome === 'accepted') showToast('📱 Crop Bot installed! Find it on your home screen.');
    });
}

if (pwaDismissBtn) {
    pwaDismissBtn.addEventListener('click', () => {
        pwaBanner.classList.add('hidden');
        localStorage.setItem('pwaBannerDismissed', '1');
    });
}

window.addEventListener('appinstalled', () => {
    pwaBanner.classList.add('hidden');
    showToast('📱 Crop Bot installed successfully!');
});

// Handle PWA shortcuts (start_url shortcuts)
const urlParams = new URLSearchParams(window.location.search);
if (urlParams.get('shortcut') === 'ask') {
    startBtn && startBtn.click();
} else if (urlParams.get('shortcut') === 'calendar') {
    startBtn && startBtn.click();
    setTimeout(() => document.getElementById('btn-calendar-sidebar') && document.getElementById('btn-calendar-sidebar').click(), 300);
}

// ==================== Quota Bar ====================
const quotaBar = document.getElementById('quota-bar');
const quotaText = document.getElementById('quota-text');

function updateQuotaBar(remaining) {
    if (!quotaBar || remaining == null) return;
    quotaBar.classList.remove('hidden', 'quota-low', 'quota-empty');
    if (remaining === 0) {
        quotaBar.classList.add('quota-empty');
        quotaText.textContent = 'No free questions left today — resets at midnight';
    } else if (remaining <= 2) {
        quotaBar.classList.add('quota-low');
        quotaText.textContent = `⚠️ Only ${remaining} free question${remaining === 1 ? '' : 's'} left today`;
    } else {
        quotaText.textContent = `${remaining} free question${remaining === 1 ? '' : 's'} remaining today`;
    }
}

// ==================== Paywall Modal ====================
const paywallModal = document.getElementById('paywall-modal');
const closePaywall = document.getElementById('close-paywall');
const paywallShareBtn = document.getElementById('paywall-share-btn');
const paywallCountdown = document.getElementById('paywall-countdown');

function showPaywall() {
    if (!paywallModal) return;
    paywallModal.classList.remove('hidden');
    updatePaywallCountdown();
}

function updatePaywallCountdown() {
    if (!paywallCountdown) return;
    const now = new Date();
    const midnight = new Date(now);
    midnight.setHours(24, 0, 0, 0);
    const diff = midnight - now;
    const h = Math.floor(diff / 3600000);
    const m = Math.floor((diff % 3600000) / 60000);
    paywallCountdown.textContent = `${h}h ${m}m until reset`;
}

if (closePaywall) closePaywall.addEventListener('click', () => paywallModal.classList.add('hidden'));
if (paywallModal) paywallModal.addEventListener('click', (e) => { if (e.target === paywallModal) paywallModal.classList.add('hidden'); });

if (paywallShareBtn) {
    paywallShareBtn.addEventListener('click', async () => {
        const shareData = {
            title: 'Crop Bot — Free AI Farming Assistant',
            text: 'Get free farming advice, weather alerts, and crop disease diagnosis in your language! Built by a 12-year-old student from India.',
            url: 'http://13.61.11.239:5000/',
        };
        try {
            if (navigator.share) {
                await navigator.share(shareData);
                showToast('🙏 Thank you for sharing!');
            } else {
                await navigator.clipboard.writeText(shareData.url);
                showToast('🔗 Link copied! Share it with fellow farmers.');
            }
        } catch (e) { /* user cancelled */ }
    });
}

// ==================== Crop Calendar ====================
const calendarModal = document.getElementById('calendar-modal');
const closeCalendar = document.getElementById('close-calendar');
const calendarBody = document.getElementById('calendar-body');
const calendarCropInfo = document.getElementById('calendar-crop-info');
const calGenerateBtn = document.getElementById('cal-generate-btn');
const calCropInput = document.getElementById('cal-crop-input');
const calDistrictInput = document.getElementById('cal-district-input');
const btnCalendarSidebar = document.getElementById('btn-calendar-sidebar');

function openCalendarModal() {
    if (!calendarModal) return;
    calendarModal.classList.remove('hidden');
    // Pre-fill from farm profile
    const profile = JSON.parse(localStorage.getItem(LS_PROFILE) || '{}');
    if (calCropInput && profile.crop && !calCropInput.value) calCropInput.value = profile.crop;
    if (calDistrictInput && profile.district && !calDistrictInput.value) calDistrictInput.value = profile.district;
}

const shareBtnSidebar = document.getElementById('share-btn-sidebar');
if (shareBtnSidebar) {
    shareBtnSidebar.addEventListener('click', async () => {
        const shareData = {
            title: 'Crop Bot — Free AI Farming Assistant',
            text: '🌾 Get free farming advice, crop disease diagnosis, weather alerts & more in 55+ languages! Built by a 12-year-old student from India.',
            url: 'http://13.61.11.239:5000/',
        };
        try {
            if (navigator.share) {
                await navigator.share(shareData);
            } else {
                await navigator.clipboard.writeText(shareData.url);
                showToast('🔗 Link copied! Share it with farmers on WhatsApp.');
            }
        } catch (e) { /* user cancelled */ }
    });
}

if (btnCalendarSidebar) btnCalendarSidebar.addEventListener('click', openCalendarModal);
if (closeCalendar) closeCalendar.addEventListener('click', () => calendarModal.classList.add('hidden'));
if (calendarModal) calendarModal.addEventListener('click', (e) => { if (e.target === calendarModal) calendarModal.classList.add('hidden'); });

function renderCalendarGrid(data) {
    const months = Array.isArray(data) ? data : null;
    if (!months) return null;
    return `<div class="calendar-grid">${months.map((m) => `
        <div class="cal-month-card">
            <div class="cal-month-name">📅 ${m.month || ''}</div>
            ${m.season ? `<span class="cal-season-badge">${m.season}</span>` : ''}
            <ul class="cal-activities">${(m.activities || []).map((a) => `<li>${a}</li>`).join('')}</ul>
            ${m.watch ? `<div class="cal-watch">⚠️ ${m.watch}</div>` : ''}
            ${m.tip ? `<div class="cal-tip">💡 ${m.tip}</div>` : ''}
        </div>`).join('')}</div>`;
}

async function generateCalendar() {
    if (!calCropInput || !calendarBody) return;
    const crop = calCropInput.value.trim();
    const district = calDistrictInput ? calDistrictInput.value.trim() : '';
    if (!crop) { showToast('Enter a crop name first'); calCropInput.focus(); return; }

    calendarBody.innerHTML = '<div class="cal-loading">🌱 Generating your calendar… this may take 15–20 seconds</div>';
    if (calendarCropInfo) calendarCropInfo.textContent = `Crop: ${crop}${district ? ' · ' + district : ''}`;
    if (calGenerateBtn) calGenerateBtn.disabled = true;

    try {
        const url = `${apiOrigin()}/crop-calendar?crop=${encodeURIComponent(crop)}${district ? '&district=' + encodeURIComponent(district) : ''}`;
        const r = await fetch(url);
        const d = await r.json();
        if (d.error) {
            calendarBody.innerHTML = `<p style="color:var(--danger);padding:16px">❌ ${d.error}</p>`;
        } else if (d.calendar) {
            const grid = renderCalendarGrid(d.calendar);
            calendarBody.innerHTML = grid || `<div class="calendar-text-fallback">${d.calendar}</div>`;
        } else if (d.calendar_text) {
            calendarBody.innerHTML = `<div class="calendar-text-fallback">${d.calendar_text}</div>`;
        }
    } catch (e) {
        calendarBody.innerHTML = '<p style="color:var(--danger);padding:16px">❌ Could not connect to server.</p>';
    } finally {
        if (calGenerateBtn) calGenerateBtn.disabled = false;
    }
}

if (calGenerateBtn) calGenerateBtn.addEventListener('click', generateCalendar);
if (calCropInput) calCropInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') generateCalendar(); });

// ==================== Initialize ====================
const savedLang = localStorage.getItem(LS_LANG);
if (savedLang && langSelect) langSelect.value = savedLang;
loadFarmProfileIntoForm();
loadDatasets();
refreshProviderStatus();
initVoiceRecognition();
renderHistory();
// Pre-load voices so they are ready for first TTS call
if (synthesis) synthesis.getVoices();
console.log('🌾 Crop Bot initialized successfully!');
// no duplicate submit handler here; main one above has developer fallback logic.
