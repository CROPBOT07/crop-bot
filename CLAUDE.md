# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Run the development server:**
```
python server.py
```

**Run with gunicorn (production-like):**
```
gunicorn server:app
```

**Rebuild farming datasets (curated only, ~10 seconds):**
```
$env:SKIP_HF=1; python fetch_farming_datasets.py
```

**Rebuild datasets with HuggingFace downloads (~2-5 minutes):**
```
python fetch_farming_datasets.py
```

**Validate all loaded datasets:**
```
python train_datasets.py
```

## Architecture

### Request Flow
1. Browser sends chat message → `POST /api/chat` in [server.py](server.py)
2. Server builds system prompt by combining:
   - Base farming persona + language instruction (55+ languages via `_language_instruction()`)
   - Farm profile context from the user's saved profile
   - RAG chunks from `datasets/` via `build_context()` in [dataset_loader.py](dataset_loader.py)
   - Injected gov-scheme snippets and market data when keywords match
3. System prompt + user message sent to first available AI provider (waterfall: DeepSeek → OpenAI → Groq → Anthropic)
4. Answer returned to frontend

### Key Modules
- **[server.py](server.py)**: Flask app, AI provider waterfall, route handlers (`/api/chat`, `/api/weather`, `/api/insights`, `/api/image-analysis`, `/api/datasets`), TTL cache, gov-scheme/market injection
- **[dataset_loader.py](dataset_loader.py)**: Loads all `datasets/*.json` on startup; keyword+word-overlap scoring (`score = kw_overlap×3 + text_overlap×1`); returns top-5 chunks ≤3500 chars for the system prompt
- **[weather_intel.py](weather_intel.py)**: Open-Meteo API (no key needed), rule-based farm alerts (rain, frost, heat warnings)
- **[vision_crop.py](vision_crop.py)**: Optional crop-photo analysis via OpenAI GPT-4o-mini (requires `OPENAI_API_KEY`)
- **[script.js](script.js)**: Voice I/O, farm profile persistence (localStorage), weather, chat history, image upload
- **[fetch_farming_datasets.py](fetch_farming_datasets.py)**: Downloads HuggingFace/Kaggle datasets and converts them to the JSON chunk format used by `dataset_loader.py`

### Dataset Format
All files in `datasets/*.json` (except `manifest.json` and `_built_index.json`) are auto-loaded. Schema:
```json
{
  "id": "unique_id",
  "name": "Display Name",
  "chunks": [
    { "text": "...", "keywords": ["kw1", "kw2"] }
  ]
}
```

### Environment Variables
Set in `.env` (local) or Render dashboard (production):
- `DEEPSEEK_API_KEY` — primary AI provider
- `OPENAI_API_KEY` — fallback + image analysis
- `GROQ_API_KEY` — additional fallback
- `ANTHROPIC_API_KEY` — additional fallback
- `OPENWEATHER_API_KEY` — weather (Open-Meteo is keyless; this is optional)
- `OPENAI_MODEL` — override model (default: `gpt-3.5-turbo`)

At least one AI provider key must be set or the server will warn and return errors.

### Deployment
Hosted on Render.com. `render.yaml` and `Procfile` both use `gunicorn server:app`. The `.github/workflows/deploy.yml` auto-deploys on push to `main`. `keep_alive.py` pings the service to prevent Render free-tier sleep.
