from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import os
import json
import time
import hashlib
import logging
from datetime import date
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple
from dotenv import load_dotenv

from dataset_loader import (
    DATASETS_DIR,
    build_context,
    load_all_datasets,
    list_dataset_metadata,
)
from weather_intel import build_alerts, fetch_weather, summarize_for_prompt
from vision_crop import analyze_crop_image

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__, static_folder='.')
CORS(app)

FREE_DAILY_LIMIT = 5
_query_counts: Dict[str, Dict[str, Any]] = {}


def _get_client_ip() -> str:
    xff = request.headers.get('X-Forwarded-For', '')
    return xff.split(',')[0].strip() if xff else (request.remote_addr or 'unknown')


def _check_rate_limit(ip: str) -> Tuple[bool, int]:
    """Returns (allowed, queries_remaining_after_this_one)."""
    today = str(date.today())
    entry = _query_counts.get(ip)
    if entry is None or entry['date'] != today:
        _query_counts[ip] = {'date': today, 'count': 1}
        return True, FREE_DAILY_LIMIT - 1
    if entry['count'] >= FREE_DAILY_LIMIT:
        return False, 0
    entry['count'] += 1
    return True, FREE_DAILY_LIMIT - entry['count']


# ── 1. Conversation Memory ────────────────────────────────────
# session_id -> list of {role, content} (max last 6 messages = 3 exchanges)
_sessions: Dict[str, List[Dict[str, str]]] = defaultdict(list)
MAX_HISTORY = 6  # 3 user + 3 assistant turns

def _get_session_history(session_id: str) -> List[Dict[str, str]]:
    return _sessions.get(session_id, [])

def _save_to_session(session_id: str, question: str, answer: str) -> None:
    if not session_id:
        return
    history = _sessions[session_id]
    history.append({'role': 'user', 'content': question})
    history.append({'role': 'assistant', 'content': answer})
    # Keep only last MAX_HISTORY messages
    if len(history) > MAX_HISTORY:
        _sessions[session_id] = history[-MAX_HISTORY:]


# ── 2. Response Cache ─────────────────────────────────────────
# hash -> (timestamp, answer, provider)
_response_cache: Dict[str, Tuple[float, str, str]] = {}
CACHE_TTL = 3600  # 1 hour

def _cache_key(question: str, farm_profile: str, dataset: str, lang: str) -> str:
    raw = f"{question.lower().strip()}|{farm_profile}|{dataset}|{lang}"
    return hashlib.md5(raw.encode()).hexdigest()

def _get_cached(key: str) -> Optional[Tuple[str, str]]:
    entry = _response_cache.get(key)
    if entry and (time.time() - entry[0]) < CACHE_TTL:
        return entry[1], entry[2]  # answer, provider
    return None

def _set_cache(key: str, answer: str, provider: str) -> None:
    _response_cache[key] = (time.time(), answer, provider)
    # Evict old entries if cache grows too large
    if len(_response_cache) > 1000:
        cutoff = time.time() - CACHE_TTL
        stale = [k for k, v in _response_cache.items() if v[0] < cutoff]
        for k in stale:
            del _response_cache[k]


# ── 3. Circuit Breaker ────────────────────────────────────────
# provider_name -> {failures: int, last_failure: float, open_until: float}
_circuit: Dict[str, Dict[str, float]] = {}
CB_FAILURE_THRESHOLD = 3
CB_OPEN_SECONDS = 300  # skip provider for 5 minutes after 3 failures

def _circuit_allow(name: str) -> bool:
    state = _circuit.get(name)
    if not state:
        return True
    if time.time() < state.get('open_until', 0):
        logger.info('Circuit breaker OPEN for %s — skipping', name)
        return False
    return True

def _circuit_success(name: str) -> None:
    if name in _circuit:
        del _circuit[name]

def _circuit_failure(name: str) -> None:
    state = _circuit.setdefault(name, {'failures': 0, 'open_until': 0})
    state['failures'] = state.get('failures', 0) + 1
    state['last_failure'] = time.time()
    if state['failures'] >= CB_FAILURE_THRESHOLD:
        state['open_until'] = time.time() + CB_OPEN_SECONDS
        logger.warning('Circuit breaker OPENED for %s for %ds', name, CB_OPEN_SECONDS)

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Curated knowledge datasets (JSON). Run: python train_datasets.py
FARMING_DATASETS = load_all_datasets()
if FARMING_DATASETS:
    print(f"[datasets] Loaded {len(FARMING_DATASETS)} farming dataset(s) from {DATASETS_DIR}")
else:
    print(f"[datasets] No datasets in {DATASETS_DIR} - answers use the base assistant prompt only")

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def ttl_cache(seconds: int):
    cache: Dict[Tuple, Tuple[float, Any]] = {}

    def decorator(func):
        def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            now = time.time()
            if key in cache:
                ts, value = cache[key]
                if now - ts < seconds:
                    return value
            result = func(*args, **kwargs)
            cache[key] = (now, result)
            return result

        return wrapper

    return decorator


@ttl_cache(10 * 60)  # 10 minutes caching
def fetch_weather_cached(lat: float, lon: float):
    return fetch_weather(lat, lon)


@ttl_cache(10 * 60)
def get_insights_data(lat: Optional[float], lon: Optional[float], crop: str, district: str):
    weather_alerts = []
    if lat is not None and lon is not None:
        raw = fetch_weather_cached(lat, lon)
        if raw:
            weather_alerts = build_alerts(raw)
    return {
        'weather_alerts': weather_alerts,
        'proactive_tips': [],
        'market_snapshot': SAMPLE_MARKET_DATA,
    }


def _load_json(name: str) -> Dict[str, Any]:
    path = os.path.join(DATA_DIR, name)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


GOV_SCHEMES_DATA = _load_json("gov_schemes.json")
SAMPLE_MARKET_DATA = _load_json("sample_market.json")


def _format_farm_profile(profile: Optional[Dict[str, Any]]) -> str:
    if not profile or not isinstance(profile, dict):
        return ""
    lines: List[str] = ["Personalized farm profile (tailor advice to this):"]
    for key, label in (
        ("crop", "Main crop"),
        ("soil", "Soil type"),
        ("land_size", "Land size"),
        ("irrigation", "Irrigation"),
        ("district", "District / region"),
    ):
        v = profile.get(key)
        if v:
            lines.append(f"- {label}: {v}")
    return "\n".join(lines) if len(lines) > 1 else ""


def _language_instruction(lang: Optional[str]) -> str:
    if not lang or not isinstance(lang, str):
        return ""
    l = lang.lower().split("-")[0]  # normalise: "pt-br" → "pt", "zh-cn" → "zh"
    full = lang.lower()             # keep full tag for regional variants

    _LANG_MAP: Dict[str, str] = {
        # Indian subcontinent
        "hi": "Language: respond in Hindi using simple farmer-friendly words (Devanagari script). Avoid technical jargon.",
        "pa": "Language: respond in Punjabi using Gurmukhi script with simple everyday words.",
        "ta": "Language: respond in Tamil (தமிழ்) with simple, clear words suitable for farmers.",
        "te": "Language: respond in Telugu (తెలుగు) with simple, clear words suitable for farmers.",
        "kn": "Language: respond in Kannada (ಕನ್ನಡ) with simple words suitable for farmers.",
        "bn": "Language: respond in Bengali (বাংলা) with simple, clear language.",
        "mr": "Language: respond in Marathi (मराठी) with simple words suited for farmers.",
        "gu": "Language: respond in Gujarati (ગુજરાતી) with simple, practical language.",
        "ml": "Language: respond in Malayalam (മലയാളം) with simple, clear words.",
        "ur": "Language: respond in Urdu (اردو) using Nastaliq script and simple everyday words.",
        "or": "Language: respond in Odia (ଓଡ଼ିଆ) with simple language suited for farmers.",
        "as": "Language: respond in Assamese (অসমীয়া) with simple, clear words.",
        "ne": "Language: respond in Nepali (नेपाली) with simple words suitable for farmers.",
        "si": "Language: respond in Sinhala (සිංහල) with simple, clear language.",
        # East Asian
        "zh": "Language: respond in Chinese. Use Simplified Chinese (简体中文) unless context suggests Traditional. Keep language practical and clear.",
        "ja": "Language: respond in Japanese (日本語) using polite but simple language (です/ます form). Avoid overly technical kanji where hiragana suffices.",
        "ko": "Language: respond in Korean (한국어) using polite speech level (합쇼체) and simple vocabulary.",
        # Southeast Asian
        "id": "Language: respond in Indonesian (Bahasa Indonesia) with clear, simple language.",
        "ms": "Language: respond in Malay (Bahasa Melayu) with simple, practical language.",
        "th": "Language: respond in Thai (ภาษาไทย) with polite, simple language.",
        "vi": "Language: respond in Vietnamese (Tiếng Việt) with simple, clear language.",
        "fil": "Language: respond in Filipino/Tagalog with simple, clear language.",
        "my": "Language: respond in Burmese (မြန်မာဘာသာ) with simple language.",
        "km": "Language: respond in Khmer (ខ្មែរ) with simple, clear language.",
        # Middle East & Central Asia
        "ar": "Language: respond in Arabic (العربية) using Modern Standard Arabic (فصحى) with simple vocabulary. Right-to-left script.",
        "fa": "Language: respond in Persian/Farsi (فارسی) with simple, clear language. Right-to-left script.",
        "he": "Language: respond in Hebrew (עברית) with simple, practical language. Right-to-left script.",
        "tr": "Language: respond in Turkish (Türkçe) with simple, farmer-friendly words.",
        "az": "Language: respond in Azerbaijani (Azərbaycan dili) with simple language.",
        "kk": "Language: respond in Kazakh (Қазақ тілі) with simple, clear language.",
        "uz": "Language: respond in Uzbek (O'zbek tili) with simple, practical language.",
        # African
        "sw": "Language: respond in Swahili (Kiswahili) with simple, clear language.",
        "ha": "Language: respond in Hausa with simple, practical language.",
        "am": "Language: respond in Amharic (አማርኛ) with simple language.",
        "yo": "Language: respond in Yoruba (Yorùbá) with simple, clear language.",
        "ig": "Language: respond in Igbo with simple, practical language.",
        "af": "Language: respond in Afrikaans with simple language.",
        "zu": "Language: respond in Zulu (isiZulu) with simple, clear language.",
        "so": "Language: respond in Somali (Soomaali) with simple language.",
        # European
        "es": "Language: respond in Spanish (Español) with simple, practical language.",
        "fr": "Language: respond in French (Français) with simple, clear language.",
        "de": "Language: respond in German (Deutsch) with simple, practical language.",
        "pt": "Language: respond in Portuguese (Português) with simple language.",
        "it": "Language: respond in Italian (Italiano) with simple, clear language.",
        "ru": "Language: respond in Russian (Русский) with simple, practical language.",
        "pl": "Language: respond in Polish (Polski) with simple language.",
        "nl": "Language: respond in Dutch (Nederlands) with simple, clear language.",
        "el": "Language: respond in Greek (Ελληνικά) with simple language.",
        "sv": "Language: respond in Swedish (Svenska) with simple, clear language.",
        "no": "Language: respond in Norwegian (Norsk) with simple language.",
        "da": "Language: respond in Danish (Dansk) with simple, clear language.",
        "fi": "Language: respond in Finnish (Suomi) with simple language.",
        "ro": "Language: respond in Romanian (Română) with simple, clear language.",
        "uk": "Language: respond in Ukrainian (Українська) with simple language.",
        "cs": "Language: respond in Czech (Čeština) with simple, clear language.",
        "sk": "Language: respond in Slovak (Slovenčina) with simple language.",
        "hu": "Language: respond in Hungarian (Magyar) with simple, clear language.",
        "bg": "Language: respond in Bulgarian (Български) with simple language.",
        "hr": "Language: respond in Croatian (Hrvatski) with simple, clear language.",
        "sr": "Language: respond in Serbian (Српски) with simple language.",
        "ca": "Language: respond in Catalan (Català) with simple, clear language.",
        "lt": "Language: respond in Lithuanian (Lietuvių) with simple language.",
        "lv": "Language: respond in Latvian (Latviešu) with simple, clear language.",
        "et": "Language: respond in Estonian (Eesti) with simple language.",
    }

    instruction = _LANG_MAP.get(l)
    if instruction:
        return instruction
    # English variants — no special instruction needed
    if l == "en":
        return ""
    # Unknown language code — ask the model to match it
    return f"Language: respond in the user's selected language (code: {lang}). Keep wording simple and farmer-friendly."


def _scheme_and_market_snippets(question: str) -> str:
    q = question.lower()
    parts: List[str] = []

    if any(
        k in q
        for k in (
            "scheme",
            "pm-kisan",
            "pm kisan",
            "kisan",
            "pmfby",
            "fasal",
            "bima",
            "insurance",
            "yojana",
            "government",
            "sarkar",
        )
    ):
        schemes = GOV_SCHEMES_DATA.get("schemes") or []
        if schemes:
            lines = ["Government schemes (short reference — verify eligibility on official portals):"]
            for s in schemes:
                lines.append(
                    f"- {s.get('name', '')}: {s.get('short', '')} Eligibility: {s.get('eligibility', '')}"
                )
            parts.append("\n".join(lines))

    if any(k in q for k in ("price", "mandi", "market", "sell", "rate", "buyer", "profit")):
        note = SAMPLE_MARKET_DATA.get("note", "")
        crops = SAMPLE_MARKET_DATA.get("crops") or []
        if crops:
            lines = [
                "Market / mandi (sample demo data — integrate live AGMARKNET/API for production):",
                note,
            ]
            for c in crops:
                lines.append(
                    f"- {c.get('name', '')}: ~{c.get('price', '')} {SAMPLE_MARKET_DATA.get('unit', '')}, "
                    f"trend {c.get('trend', '')}. Tip: {c.get('tip', '')}"
                )
            parts.append("\n".join(lines))

    return "\n\n".join(parts)


# AI Provider Configurations
# Supports fallback across multiple providers for reliability.
AI_PROVIDERS: List[Dict[str, Any]] = []

if os.getenv('DEEPSEEK_API_KEY'):
    AI_PROVIDERS.append({
        'name': 'DeepSeek',
        'api_url': 'https://api.deepseek.com/v1/chat/completions',
        'api_key': os.getenv('DEEPSEEK_API_KEY', ''),
        'model': 'deepseek-chat',
        'headers': lambda key: {
            'Authorization': f'Bearer {key}',
            'Content-Type': 'application/json'
        }
    })

if os.getenv('OPENAI_API_KEY'):
    AI_PROVIDERS.append({
        'name': 'OpenAI',
        'api_url': 'https://api.openai.com/v1/chat/completions',
        'api_key': os.getenv('OPENAI_API_KEY', ''),
        'model': os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo'),
        'headers': lambda key: {
            'Authorization': f'Bearer {key}',
            'Content-Type': 'application/json'
        }
    })

if os.getenv('GROQ_API_KEY'):
    AI_PROVIDERS.append({
        'name': 'GROQ',
        'api_url': 'https://api.groq.com/v1/chat/completions',
        'api_key': os.getenv('GROQ_API_KEY', ''),
        'model': os.getenv('GROQ_MODEL', 'groq-1.1-mini'),
        'headers': lambda key: {
            'Authorization': f'Bearer {key}',
            'Content-Type': 'application/json'
        }
    })

if os.getenv('ANTHROPIC_API_KEY'):
    AI_PROVIDERS.append({
        'name': 'Anthropic',
        'api_url': 'https://api.anthropic.com/v1/complete',
        'api_key': os.getenv('ANTHROPIC_API_KEY', ''),
        'model': os.getenv('ANTHROPIC_MODEL', 'claude-3.5-mini'),
        'headers': lambda key: {
            'x-api-key': key,
            'Content-Type': 'application/json'
        },
        'custom_format': True
    })

if not AI_PROVIDERS:
    logger.warning('No AI providers are configured. Add DEEPSEEK_API_KEY, OPENAI_API_KEY, GROQ_API_KEY, or ANTHROPIC_API_KEY to .env')


def call_deepseek_openai_groq(provider: Dict, question: str, system_prompt: str, history: Optional[List[Dict]] = None) -> Tuple[bool, str]:
    """Call DeepSeek, OpenAI, or Groq API (they use same format)"""
    try:
        headers = provider['headers'](provider['api_key'])
        messages = [{'role': 'system', 'content': system_prompt}]
        if history:
            messages.extend(history[:-1])  # add prior turns, exclude last user msg
        messages.append({'role': 'user', 'content': question})
        payload = {
            'model': provider['model'],
            'messages': messages,
            'temperature': 0.7,
            'max_tokens': 1000
        }
        
        # Try with longer timeout and retry logic
        max_retries = 2
        response = None
        for attempt in range(max_retries):
            try:
                response = requests.post(provider['api_url'], json=payload, headers=headers, timeout=60)
                break  # Success, exit retry loop
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    print(f"   ⏳ Timeout on attempt {attempt + 1}, retrying...")
                    continue
                else:
                    return False, 'Request timeout (connection took too long after retries)'
            except requests.exceptions.ConnectionError:
                if attempt < max_retries - 1:
                    print(f"   🔄 Connection error on attempt {attempt + 1}, retrying...")
                    continue
                else:
                    return False, 'Connection error: Unable to reach API server'
        
        # Process the response (should be defined if we got here)
        if response and response.status_code == 200:
            result = response.json()
            answer = result['choices'][0]['message']['content']
            return True, answer
        else:
            # Try to get the actual error message from the API response
            try:
                error_data = response.json()
                error_message = error_data.get('error', {}).get('message', 'Unknown error')
                error_type = error_data.get('error', {}).get('type', '')
                error_code = error_data.get('error', {}).get('code', '')
                
                # Build a detailed error message
                detailed_error = error_message
                if error_type:
                    detailed_error += f" (type: {error_type})"
                if error_code:
                    detailed_error += f" (code: {error_code})"
                
                return False, detailed_error
            except:
                # If we can't parse JSON, use status code and raw text
                if response.status_code == 401:
                    return False, 'Invalid API key'
                elif response.status_code == 429:
                    return False, 'Rate limit exceeded'
                elif response.status_code == 402:
                    return False, 'Insufficient credits or payment required'
                else:
                    return False, f'API error {response.status_code}: {response.text[:200]}'
            
    except requests.exceptions.Timeout:
        return False, 'Request timeout (connection took too long)'
    except requests.exceptions.ConnectionError as e:
        return False, f'Connection error: Unable to reach API server - {str(e)}'
    except Exception as e:
        return False, f'Error: {str(e)}'

def call_anthropic(provider: Dict, question: str, system_prompt: str) -> Tuple[bool, str]:
    """Call Anthropic Claude API (different format)"""
    try:
        headers = provider['headers'](provider['api_key'])
        payload = {
            'model': provider['model'],
            'max_tokens': 1000,
            'system': system_prompt,
            'messages': [
                {'role': 'user', 'content': question}
            ]
        }
        
        response = requests.post(provider['api_url'], json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            answer = result['content'][0]['text']
            return True, answer
        else:
            # Try to get the actual error message from the API response
            try:
                error_data = response.json()
                error_message = error_data.get('error', {}).get('message', 'Unknown error')
                error_type = error_data.get('error', {}).get('type', '')
                
                detailed_error = error_message
                if error_type:
                    detailed_error += f" (type: {error_type})"
                
                return False, detailed_error
            except:
                # If we can't parse JSON, use status code
                if response.status_code == 401:
                    return False, 'Invalid API key'
                elif response.status_code == 429:
                    return False, 'Rate limit exceeded'
                else:
                    return False, f'API error {response.status_code}: {response.text[:200]}'
            
    except requests.exceptions.Timeout:
        return False, 'Request timeout'
    except Exception as e:
        return False, f'Error: {str(e)}'

def get_ai_response(
    question: str,
    dataset_scope: str = "all",
    *,
    weather_summary: Optional[str] = None,
    farm_profile_text: str = "",
    language_instruction: str = "",
    schemes_market_text: str = "",
    image_analysis: Optional[str] = None,
    history: Optional[List[Dict]] = None,
) -> Tuple[Optional[str], Optional[str], str]:
    """
    Try multiple AI providers in order until one succeeds.
    dataset_scope: 'all' or a dataset id — relevant chunks are injected as training context (RAG).
    Returns: (answer, provider_name, error_message)
    """
    base_prompt = """You are a decision-oriented farming assistant for India. Give practical, local-context-aware
    advice when context is provided. Prefer short paragraphs and bullet steps. Avoid generic textbook-only answers
    when weather, profile, or photo context exists. Mention when forecasts are model-based (not official IMD) if relevant.
    Be clear and encouraging."""

    scope = (dataset_scope or "all").strip().lower()
    if scope not in FARMING_DATASETS and scope != "all":
        scope = "all"

    rag = build_context(question, FARMING_DATASETS, scope)
    blocks: List[str] = [base_prompt]

    if language_instruction:
        blocks.append(language_instruction)

    if farm_profile_text:
        blocks.append(farm_profile_text)

    if weather_summary:
        blocks.append(
            "Hyperlocal weather context (Open-Meteo model — complement with official IMD/local advisories for critical decisions):\n"
            + weather_summary
        )

    if schemes_market_text:
        blocks.append(schemes_market_text)

    if image_analysis:
        blocks.append(
            "Crop/plant photo analysis (vision model — severity is indicative; verify in field):\n" + image_analysis
        )

    if rag:
        blocks.append(
            "Curated reference notes from training datasets (use when relevant):\n---\n" + rag
        )

    system_prompt = "\n\n".join(blocks)
    
    failed_providers = []

    for provider in AI_PROVIDERS:
        name = provider['name']

        # Skip if no API key provided
        if not provider['api_key']:
            failed_providers.append(f"{name} (no API key)")
            continue

        # Circuit breaker — skip recently failed providers
        if not _circuit_allow(name):
            failed_providers.append(f"{name} (circuit open)")
            continue

        logger.info('Trying provider %s', name)

        # Call appropriate API based on provider
        if provider.get('custom_format'):
            success, result = call_anthropic(provider, question, system_prompt)
        else:
            success, result = call_deepseek_openai_groq(provider, question, system_prompt, history=history)

        if success:
            _circuit_success(name)
            logger.info('Success with provider %s', name)
            return result, name, ''
        else:
            _circuit_failure(name)
            logger.warning('Provider %s failed: %s', name, result)
            failed_providers.append(f"{name} ({result})")
            continue
    
    # All providers failed
    error_msg = 'All AI providers failed. '
    if failed_providers:
        error_msg += f'Failed providers: {", ".join(failed_providers)}. '
    error_msg += 'Please check your API keys in the .env file and ensure at least one has available credits.'
    return None, None, error_msg

@app.errorhandler(Exception)
def handle_exception(e):
    logger.error('Unhandled exception: %s', str(e), exc_info=True)
    return jsonify({'error': 'Internal server error'}), 500


@app.route('/ask', methods=['POST'])
def ask_question():
    try:
        data = request.json or {}
        question = (data.get('question') or '').strip()
        if not question:
            return jsonify({'error': 'No question provided'}), 400
        if len(question) > 1200:
            return jsonify({'error': 'Question is too long (max 1200 characters)'}), 400

        ip = _get_client_ip()
        allowed, remaining = _check_rate_limit(ip)
        if not allowed:
            return jsonify({
                'error': 'quota_exceeded',
                'message': f'You have used all {FREE_DAILY_LIMIT} free questions for today. Come back tomorrow for more free questions!',
                'limit': FREE_DAILY_LIMIT,
            }), 429

        logger.info('Received /ask request. question=%s', (question[:120] + '...') if len(question) > 120 else question)
        raw_dataset = data.get('dataset', 'all')
        eff_dataset = (raw_dataset or 'all').strip().lower()
        if eff_dataset not in FARMING_DATASETS and eff_dataset != 'all':
            eff_dataset = 'all'

        weather_summary: Optional[str] = None
        lat, lon = data.get('lat'), data.get('lon')
        if lat is not None and lon is not None:
            try:
                wf = fetch_weather(float(lat), float(lon))
                if wf:
                    weather_summary = summarize_for_prompt(wf, float(lat), float(lon))
            except (TypeError, ValueError):
                pass

        farm_profile_text = _format_farm_profile(data.get('farm_profile'))
        lang = data.get('language') or data.get('lang')
        language_instruction = _language_instruction(lang if isinstance(lang, str) else None)
        schemes_market_text = _scheme_and_market_snippets(question)
        session_id = (data.get('session_id') or '').strip()

        image_analysis: Optional[str] = None
        img_b64 = data.get('image_base64')
        img_mime = data.get('image_mime') or 'image/jpeg'
        has_image = isinstance(img_b64, str) and img_b64.strip()
        if has_image:
            image_analysis = analyze_crop_image(img_b64.strip(), str(img_mime))
            if not image_analysis:
                image_analysis = (
                    "User attached a crop photo, but image analysis is unavailable "
                    "(set OPENAI_API_KEY on the server for automatic photo review). "
                    "Ask them to describe leaf/stem/leaf symptoms in words."
                )

        # Check response cache (skip if image attached — images are unique)
        cache_key = _cache_key(question, farm_profile_text, eff_dataset, lang or 'en')
        cached = None if has_image else _get_cached(cache_key)
        if cached:
            cached_answer, cached_provider = cached
            logger.info('Cache hit for question (provider was %s)', cached_provider)
            if session_id:
                _save_to_session(session_id, question, cached_answer)
            return jsonify({
                'answer': cached_answer,
                'provider': cached_provider + ' (cached)',
                'dataset': eff_dataset if FARMING_DATASETS else None,
                'image_analyzed': False,
                'queries_remaining': remaining,
                'from_cache': True,
            })

        # Get conversation history for this session
        history = _get_session_history(session_id) if session_id else None

        answer, provider, error = get_ai_response(
            question,
            eff_dataset,
            weather_summary=weather_summary,
            farm_profile_text=farm_profile_text,
            language_instruction=language_instruction,
            schemes_market_text=schemes_market_text,
            image_analysis=image_analysis,
            history=history,
        )

        if answer:
            logger.info('Answer provided by %s (dataset=%s)', provider, eff_dataset)
            if not has_image:
                _set_cache(cache_key, answer, provider)
            if session_id:
                _save_to_session(session_id, question, answer)
            return jsonify({
                'answer': answer,
                'provider': provider,
                'dataset': eff_dataset if FARMING_DATASETS else None,
                'image_analyzed': bool(image_analysis),
                'queries_remaining': remaining,
            })
        else:
            logger.error('AI response failure: %s', error)
            return jsonify({'error': error}), 500

    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500


@app.route('/weather', methods=['GET'])
def weather_endpoint():
    lat = request.args.get('lat', type=float)
    lon = request.args.get('lon', type=float)
    if lat is None or lon is None:
        return jsonify({'error': 'Provide lat and lon query parameters'}), 400
    raw = fetch_weather_cached(lat, lon)
    if not raw:
        return jsonify({'error': 'Weather data unavailable'}), 502
    daily = raw.get('daily') or {}
    prec = daily.get('precipitation_sum') or []
    tomorrow_rain = float(prec[1]) if len(prec) > 1 else None
    cur = raw.get('current') or {}
    return jsonify({
        'temperature_c': cur.get('temperature_2m'),
        'humidity_pct': cur.get('relative_humidity_2m'),
        'weather_code': cur.get('weather_code'),
        'tomorrow_precip_mm': tomorrow_rain,
        'alerts': build_alerts(raw),
        'summary': summarize_for_prompt(raw, lat, lon),
    })

@app.route('/insights', methods=['GET'])
def insights_endpoint():
    lat = request.args.get('lat', type=float)
    lon = request.args.get('lon', type=float)
    crop = (request.args.get('crop') or '').strip().lower()
    district = (request.args.get('district') or '').strip()

    # Cached insights (including weather alerts)
    insights = get_insights_data(lat, lon, crop, district)
    weather_alerts = insights.get('weather_alerts', [])

    # Proactive tips based on crop
    crop_tips_map = {
        'wheat': [
            "Check for yellow rust disease during cool humid weather",
            "Apply second dose of nitrogen at tillering stage",
            "Ensure adequate irrigation at grain filling stage",
        ],
        'rice': [
            "Monitor for blast disease in humid conditions",
            "Maintain 5cm water level during tillering",
            "Scout for stem borer weekly",
        ],
        'cotton': [
            "Scout for bollworm and whitefly weekly",
            "Avoid excess nitrogen which promotes vegetative growth",
            "Check soil moisture before irrigation — cotton is drought tolerant once established",
        ],
        'tomato': [
            "Watch for early blight in wet weather",
            "Stake plants at 30cm height",
            "Apply calcium fertilizer to prevent blossom-end rot",
        ],
    }
    default_tips = [
        "Monitor crops regularly for early pest/disease signs",
        "Maintain field hygiene — remove crop debris",
        "Keep irrigation channels clear",
    ]
    proactive_tips = crop_tips_map.get(crop, default_tips)

    return jsonify({
        'weather_alerts': weather_alerts,
        'proactive_tips': proactive_tips,
        'market_snapshot': SAMPLE_MARKET_DATA,
        'schemes_count': 3,
    })


@app.route('/health', methods=['GET'])
def health():
    # Check which providers have API keys configured
    configured_providers = [p['name'] for p in AI_PROVIDERS if p['api_key']]
    return jsonify({
        'status': 'ok',
        'configured_providers': configured_providers,
        'total_providers': len(AI_PROVIDERS),
        'openai_vision': bool(os.getenv('OPENAI_API_KEY', '').strip()),
        'datasets_loaded': len(FARMING_DATASETS),
    })


@app.route('/feedback', methods=['POST'])
def feedback():
    payload = request.json or {}
    question = (payload.get('question') or '').strip()
    answer = (payload.get('answer') or '').strip()
    feedback_text = (payload.get('feedback') or '').strip()

    if not feedback_text:
        return jsonify({'error': 'Feedback text is required'}), 400

    entry = {
        'timestamp': payload.get('timestamp') or time.strftime('%Y-%m-%dT%H:%M:%S'),
        'question': question,
        'answer': answer,
        'feedback': feedback_text,
        'source': request.remote_addr,
    }

    try:
        feedback_file = os.path.join(DATA_DIR, 'feedback.jsonl')
        with open(feedback_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        return jsonify({'status': 'ok'}), 201
    except Exception as e:
        logger.error('Error saving feedback: %s', str(e), exc_info=True)
        return jsonify({'error': 'Could not save feedback'}), 500


@app.route('/datasets', methods=['GET'])
def get_datasets():
    """List available training datasets (metadata only)."""
    meta = list_dataset_metadata(FARMING_DATASETS)
    return jsonify({
        'datasets': [{'id': 'all', 'name': 'All datasets', 'chunks': sum(m['chunks'] for m in meta)}] + meta
        if meta else
        [{'id': 'all', 'name': 'All datasets', 'chunks': 0}],
    })


@app.route('/providers', methods=['GET'])
def get_providers():
    """Get list of available providers and their status"""
    providers_info = []
    for provider in AI_PROVIDERS:
        providers_info.append({
            'name': provider['name'],
            'configured': bool(provider['api_key']),
            'model': provider['model']
        })
    return jsonify({'providers': providers_info})

@app.route('/crop-calendar', methods=['GET'])
def crop_calendar():
    crop = (request.args.get('crop') or '').strip()
    district = (request.args.get('district') or '').strip()
    if not crop:
        return jsonify({'error': 'Provide crop parameter'}), 400

    location_hint = f" in {district}" if district else " in India"
    question = f"12-month farming calendar for {crop}{location_hint}"
    system_prompt = (
        "You are an expert Indian agricultural scientist. "
        "Generate a practical 12-month crop calendar as a JSON array (no markdown, just raw JSON). "
        "Each element: {\"month\": \"January\", \"season\": \"Rabi\", "
        "\"activities\": [\"...\", \"...\"], \"watch\": \"...\", \"tip\": \"...\"}. "
        "Include all 12 months. Return ONLY the JSON array."
    )

    for provider in AI_PROVIDERS:
        if not provider['api_key']:
            continue
        if provider.get('custom_format'):
            success, result = call_anthropic(provider, question, system_prompt)
        else:
            success, result = call_deepseek_openai_groq(provider, question, system_prompt)
        if success:
            result = result.strip()
            # Strip markdown code fences if present
            if result.startswith('```'):
                result = result.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
            try:
                calendar_data = json.loads(result)
                return jsonify({'calendar': calendar_data, 'crop': crop, 'district': district})
            except json.JSONDecodeError:
                return jsonify({'calendar_text': result, 'crop': crop, 'district': district})

    return jsonify({'error': 'Calendar generation failed — no AI provider available'}), 500


@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/sitemap.xml')
def sitemap():
    return send_from_directory('.', 'sitemap.xml', mimetype='application/xml')

@app.route('/robots.txt')
def robots():
    return send_from_directory('.', 'robots.txt', mimetype='text/plain')

@app.route('/<path:filename>')
def serve_static(filename):
    """Serve static files (CSS, JS) - only allow specific file types"""
    allowed_extensions = ['.html', '.css', '.js', '.json', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.mp3', '.wav', '.ogg']
    if any(filename.endswith(ext) for ext in allowed_extensions):
        return send_from_directory('.', filename)
    else:
        return jsonify({'error': 'File not found'}), 404

if __name__ == '__main__':
    print("🌾 Farming Helper Server Starting...")
    print("\n📋 Configured AI Providers:")
    configured_count = 0
    for provider in AI_PROVIDERS:
        status = "✅" if provider['api_key'] else "❌"
        print(f"  {status} {provider['name']} - {provider['model']}")
        if provider['api_key']:
            configured_count += 1
    
    if configured_count == 0:
        print("\n⚠️  WARNING: No API keys configured!")
        print("   Please add at least one API key to your .env file")
    elif configured_count == 1:
        print("\n⚠️  WARNING: Only one API key configured!")
        print("   Consider adding more API keys for better reliability")
    else:
        print(f"\n✅ {configured_count} API keys configured - fallback system ready!")
    
    print("\n💡 Tip: Add API keys to your .env file:")
    print("   DEEPSEEK_API_KEY, GROQ_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY")
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV', 'production') == 'development'
    print(f"\n🚀 Server running on http://localhost:{port}\n")
    app.run(debug=debug, host='0.0.0.0', port=port)

