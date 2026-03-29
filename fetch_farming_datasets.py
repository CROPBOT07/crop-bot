#!/usr/bin/env python3
"""
fetch_farming_datasets.py
Downloads farming datasets from HuggingFace and Kaggle,
converts them to RAG-ready JSON chunks for Crop Bot.

Usage:
    python fetch_farming_datasets.py

For Kaggle datasets, you need a Kaggle API key:
    1. Go to https://www.kaggle.com/account
    2. Click "Create New API Token"
    3. Save kaggle.json to ~/.kaggle/kaggle.json
"""

from __future__ import annotations
import json
import os
import re
import sys
import subprocess
import shutil
from pathlib import Path

# Force UTF-8 output on Windows
import io
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# ─── Config ────────────────────────────────────────────────────────────────────
DATASETS_DIR = Path("datasets")
TEMP_DIR = Path("temp_kaggle")
DATASETS_DIR.mkdir(exist_ok=True)

MAX_CHUNKS_PER_DATASET = 200   # cap to keep prompts snappy
MAX_CHUNK_CHARS = 800          # chars per chunk
HF_TIMEOUT = 60                # timeout for HF dataset download in seconds
SKIP_HUGGINGFACE = os.environ.get("SKIP_HF", "").lower() in ("1", "true", "yes")


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _pip_install(*packages: str) -> None:
    """Quietly install packages if not already present."""
    for pkg in packages:
        import_name = pkg.split("==")[0].replace("-", "_")
        try:
            __import__(import_name)
        except ImportError:
            # Skip kaggle if it's slow/network issues
            if import_name == "kaggle" and SKIP_HUGGINGFACE:
                continue
            print(f"  [install] {pkg}...")
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", pkg, "-q"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=120,
                )
            except subprocess.TimeoutExpired:
                print(f"  [timeout] {pkg} installation timed out (skipping)")
            except Exception as e:
                print(f"  [warn] {pkg}: {e} (skipping)")


def _clean(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)
    return re.sub(r"\s+", " ", text).strip()


def _chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """Split text into sentence-bounded chunks."""
    text = _clean(text)
    if len(text) <= max_chars:
        return [text]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks, current = [], ""
    for s in sentences:
        if len(current) + len(s) + 1 <= max_chars:
            current = (current + " " + s).strip()
        else:
            if current:
                chunks.append(current)
            current = s[:max_chars]
    if current:
        chunks.append(current)
    return chunks or [text[:max_chars]]


_STOP = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "must", "can", "this", "that",
    "these", "those", "it", "its", "they", "their", "them", "which", "who",
    "not", "also", "well", "good", "used", "use", "using", "help", "make",
}


def _keywords(text: str, extra: list[str] | None = None) -> list[str]:
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
    kws = list(dict.fromkeys(w for w in words if w not in _STOP))
    if extra:
        for e in extra:
            e = e.lower().strip()
            if e and e not in kws:
                kws.insert(0, e)
    return kws[:20]


def _save(dataset_id: str, name: str, chunks: list[dict], filename: str) -> int:
    """Write a dataset JSON file and return chunk count."""
    if not chunks:
        print(f"  [skip] No chunks for '{name}'")
        return 0
    # deduplicate by first 120 chars of text
    seen, unique = set(), []
    for c in chunks:
        key = c["text"][:120]
        if key not in seen:
            seen.add(key)
            unique.append(c)
    data = {"id": dataset_id, "name": name, "chunks": unique[:MAX_CHUNKS_PER_DATASET]}
    path = DATASETS_DIR / filename
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  [OK] {path.name:<45} ({len(data['chunks']):>3} chunks)")
        return len(data["chunks"])
    except Exception as e:
        print(f"  [error] Failed to save {filename}: {e}")
        return 0


# ─── HuggingFace Datasets ───────────────────────────────────────────────────────

def _hf_load(dataset_ids: list[str], split: str = "train", **kwargs):
    """Try multiple HuggingFace dataset IDs and return the first that works."""
    if SKIP_HUGGINGFACE:
        return None

    from datasets import load_dataset  # noqa
    for did in dataset_ids:
        try:
            print(f"  [download] {did} (timeout {HF_TIMEOUT}s)...")
            ds = load_dataset(did, split=split, trust_remote_code=True,
                            timeout=HF_TIMEOUT, **kwargs)
            print(f"  [OK] Loaded {did}")
            return ds
        except TimeoutError:
            print(f"  [timeout] {did} took too long")
        except Exception as exc:
            err_msg = str(exc)[:60]
            print(f"  [fail] {did}: {err_msg}")
    return None


def hf_crop_recommendation() -> int:
    print("\n[dataset] Crop Recommendation")
    ds = _hf_load([
        "Ahmed9275/Crop-Recommendation-Dataset",
        "Thewillonline/crop-recommendation-dataset",
        "Aditya-r123/Crop_Recommendation_Dataset",
    ])
    if ds is None:
        return 0

    # Group by crop label
    from collections import defaultdict
    groups: dict[str, list] = defaultdict(list)
    try:
        for row in ds:
            label = str(row.get("label") or row.get("crop") or row.get("Crop") or "unknown")
            groups[label].append(row)
    except Exception as e:
        print(f"  [error] Failed to process dataset: {e}")
        return 0

    def _avg(rows, key):
        vals = []
        for r in rows:
            for k in (key, key.capitalize(), key.upper()):
                try:
                    vals.append(float(r[k]))
                    break
                except Exception:
                    pass
        return sum(vals) / len(vals) if vals else 0

    chunks = []
    for crop, rows in groups.items():
        try:
            n, p, k = _avg(rows, "N"), _avg(rows, "P"), _avg(rows, "K")
            temp = _avg(rows, "temperature")
            hum = _avg(rows, "humidity")
            ph = _avg(rows, "ph")
            rain = _avg(rows, "rainfall")
            text = (
                f"{crop.capitalize()} grows best with nitrogen {n:.0f} kg/ha, "
                f"phosphorus {p:.0f} kg/ha, potassium {k:.0f} kg/ha. "
                f"Ideal temperature {temp:.1f}C, humidity {hum:.0f}%, "
                f"soil pH {ph:.1f}, annual rainfall {rain:.0f} mm. "
                f"Ensure balanced NPK fertilisation for high {crop} yield."
            )
            kws = [crop.lower(), "npk", "nitrogen", "phosphorus", "potassium",
                   "temperature", "humidity", "ph", "rainfall", "soil", "fertilizer"]
            chunks.append({"text": text, "keywords": kws})
        except Exception as e:
            print(f"  [warn] Could not process crop {crop}: {e}")

    return _save("crop_recommendation_hf",
                 "Crop Nutrient Requirements (HuggingFace)",
                 chunks, "crop_recommendation_hf.json")


def hf_plant_diseases() -> int:
    print("\n[HF] Plant Disease Dataset")
    ds = _hf_load([
        "Ruqiya-Bin-Safi/Plant_Disease_Information",
        "TRTwi/crop-disease-information",
        "Shadab5alam/plant_disease_data",
    ])
    if ds is None:
        return 0

    chunks = []
    for row in ds:
        disease = _clean(str(row.get("disease_name") or row.get("Disease") or row.get("label") or ""))
        crop = _clean(str(row.get("crop") or row.get("Crop") or row.get("plant") or "Plant"))
        symptoms = _clean(str(row.get("symptoms") or row.get("Symptoms") or row.get("description") or ""))
        treatment = _clean(str(row.get("treatment") or row.get("Treatment") or row.get("cure") or ""))
        cause = _clean(str(row.get("cause") or row.get("Cause") or ""))

        parts = []
        if crop and disease:
            parts.append(f"{crop} {disease}:")
        if cause:
            parts.append(f"Cause: {cause}.")
        if symptoms:
            parts.append(f"Symptoms: {symptoms}.")
        if treatment:
            parts.append(f"Treatment: {treatment}.")

        text = " ".join(parts)
        if len(text) < 40:
            continue
        for chunk in _chunk_text(text):
            kws = _keywords(chunk, extra=[crop, disease, "disease", "symptoms", "treatment"])
            chunks.append({"text": chunk, "keywords": kws})

    return _save("plant_diseases_hf",
                 "Plant Disease Guide (HuggingFace)",
                 chunks, "plant_diseases_hf.json")


def hf_agricultural_qa() -> int:
    print("\n[HF] Agricultural Q&A Dataset")
    ds = _hf_load([
        "MBZUAI/agriculture-llm-instruction-tuning",
        "OptimusCompute/agri-chat",
        "nateraw/gardening",
        "pranjali97/agriculture_instruction_dataset",
    ])
    if ds is None:
        return 0

    chunks = []
    for row in ds:
        question = _clean(str(row.get("instruction") or row.get("question") or row.get("input") or ""))
        answer = _clean(str(row.get("output") or row.get("answer") or row.get("response") or ""))
        if len(answer) < 30:
            continue
        for chunk in _chunk_text(answer):
            kws = _keywords(question + " " + chunk, extra=["farming", "agriculture"])
            chunks.append({"text": chunk, "keywords": kws})

    return _save("agri_qa_hf",
                 "Agricultural Q&A Knowledge Base (HuggingFace)",
                 chunks, "agricultural_qa_hf.json")


def hf_soil_health() -> int:
    print("\n[HF] Soil Health Dataset")
    ds = _hf_load([
        "nicholasKluge/soil-dataset",
        "Bhavesh0609/soil_dataset",
        "prashant-kr-modi/soil-types",
    ])
    if ds is None:
        return 0

    chunks = []
    for row in ds:
        parts = [f"{k}: {v}" for k, v in row.items()
                 if v is not None and str(v).strip() and k.lower() not in ("id", "index")]
        text = ". ".join(parts)
        if len(text) < 30:
            continue
        for chunk in _chunk_text(text):
            kws = _keywords(chunk, extra=["soil", "health", "nutrient"])
            chunks.append({"text": chunk, "keywords": kws})

    return _save("soil_health_hf",
                 "Soil Health & Properties (HuggingFace)",
                 chunks, "soil_health_hf.json")


def hf_fertilizer_data() -> int:
    print("\n[HF] Fertilizer Dataset")
    ds = _hf_load([
        "Devvrat15/Fertilizer-Recommendation",
        "gdabhishek48/fertilizer_prediction",
        "Coder-Analyst/fertilizer-recommendation-dataset",
    ])
    if ds is None:
        return 0

    from collections import defaultdict
    fert_col = None
    sample = next(iter(ds), None)
    if sample:
        for k in sample.keys():
            if "fertilizer" in k.lower() or "Fertilizer" in k:
                fert_col = k
                break
        if not fert_col:
            fert_col = list(sample.keys())[-1]

    groups: dict[str, list] = defaultdict(list)
    for row in ds:
        groups[str(row.get(fert_col, "Unknown"))].append(row)

    chunks = []
    for fert, rows in groups.items():
        numeric_fields = {}
        for row in rows:
            for k, v in row.items():
                if k == fert_col:
                    continue
                try:
                    numeric_fields.setdefault(k, []).append(float(v))
                except (TypeError, ValueError):
                    pass
        details = []
        for k, vals in list(numeric_fields.items())[:6]:
            avg = sum(vals) / len(vals)
            details.append(f"{k} ≈ {avg:.1f}")
        text = (f"Fertilizer '{fert}' is recommended when soil has: "
                + ", ".join(details) + ".")
        kws = _keywords(text, extra=[fert.lower(), "fertilizer", "soil", "npk", "nutrient"])
        chunks.append({"text": text, "keywords": kws})

    return _save("fertilizer_hf",
                 "Fertilizer Recommendation Guide (HuggingFace)",
                 chunks, "fertilizer_recommendation_hf.json")


def hf_crop_diseases_india() -> int:
    print("\n[HF] Indian Crop Diseases Dataset")
    ds = _hf_load([
        "FarhanMuzakki/crop-disease-dataset",
        "mrm8488/indian-crop-disease",
        "Karan9090/crop_disease_prediction",
    ])
    if ds is None:
        return 0

    chunks = []
    for row in ds:
        parts = [_clean(str(v)) for v in row.values() if v and len(str(v)) > 4]
        text = ". ".join(parts)
        if len(text) < 40:
            continue
        for chunk in _chunk_text(text):
            kws = _keywords(chunk, extra=["disease", "crop", "india", "treatment"])
            chunks.append({"text": chunk, "keywords": kws})

    return _save("crop_diseases_india_hf",
                 "Indian Crop Diseases (HuggingFace)",
                 chunks, "crop_diseases_india_hf.json")


# ─── Kaggle Setup ───────────────────────────────────────────────────────────────

def kaggle_available() -> bool:
    kaggle_json = Path.home() / ".kaggle" / "kaggle.json"
    if kaggle_json.exists():
        return True
    # Also check env vars
    if os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY"):
        return True
    print("\n[kaggle] Credentials not found (optional - Kaggle datasets will be skipped)")
    print(f"   To enable Kaggle datasets:")
    print(f"   1. Go to https://www.kaggle.com/account")
    print(f"   2. Click 'Create New API Token'")
    print(f"   3. Save kaggle.json to {kaggle_json}")
    print(f"   4. Re-run this script\n")
    return False


def _kaggle_download(slug: str, local_name: str) -> Path | None:
    """Download a Kaggle dataset and return the folder path."""
    out = TEMP_DIR / local_name
    out.mkdir(parents=True, exist_ok=True)
    try:
        import kaggle  # noqa
        print(f"  [download] {slug}...")
        kaggle.api.dataset_download_files(slug, path=str(out), unzip=True, quiet=True)
        csvs = list(out.glob("**/*.csv"))
        if csvs:
            print(f"  [OK] Downloaded {slug}")
            return out
        print(f"  [fail] No CSV files in {slug}")
        return None
    except Exception as exc:
        err_msg = str(exc)[:60]
        print(f"  [error] {slug}: {err_msg}")
        return None


def _kaggle_first_csv(folder: Path):
    """Return first CSV as a pandas DataFrame."""
    import pandas as pd  # noqa
    csvs = sorted(folder.glob("**/*.csv"))
    if not csvs:
        return None
    return pd.read_csv(csvs[0], on_bad_lines="skip")


def kaggle_crop_recommendation() -> int:
    print("\n[Kaggle] Crop Recommendation Dataset")
    folder = _kaggle_download("atharvaingle/crop-recommendation-dataset", "crop_rec")
    if not folder:
        return 0
    import pandas as pd
    df = _kaggle_first_csv(folder)
    if df is None:
        return 0

    chunks = []
    label_col = next((c for c in df.columns if "label" in c.lower() or "crop" in c.lower()), df.columns[-1])
    for crop, grp in df.groupby(label_col):
        cols = {c: grp[c] for c in df.columns if c != label_col}
        stats = {c: (float(v.min()), float(v.max())) for c, v in cols.items()
                 if pd.api.types.is_numeric_dtype(v)}
        details = ", ".join(f"{c} {lo:.1f}–{hi:.1f}" for c, (lo, hi) in list(stats.items())[:7])
        text = f"{crop}: Optimal growing conditions — {details}."
        kws = _keywords(text, extra=[str(crop).lower(), "crop", "soil", "nutrient", "grow"])
        chunks.append({"text": text, "keywords": kws})

    return _save("crop_recommendation_kaggle",
                 "Crop Growing Conditions (Kaggle)",
                 chunks, "crop_recommendation_kaggle.json")


def kaggle_fertilizer() -> int:
    print("\n[Kaggle] Fertilizer Recommendation")
    slugs = [
        "kushagra3011/fertilizer-recommendation",
        "gdabhishek48/fertilizer-prediction",
        "srinivasanravindran/fertilizer-prediction-dataset",
    ]
    folder = None
    for slug in slugs:
        folder = _kaggle_download(slug, "fertilizer")
        if folder:
            break
    if not folder:
        return 0

    import pandas as pd
    df = _kaggle_first_csv(folder)
    if df is None:
        return 0

    fert_col = next((c for c in df.columns if "fertilizer" in c.lower()), df.columns[-1])
    chunks = []
    for fert, grp in df.groupby(fert_col):
        numeric = {c: grp[c] for c in df.columns if c != fert_col and pd.api.types.is_numeric_dtype(grp[c])}
        details = ", ".join(
            f"{c} ≈ {float(v.mean()):.1f}" for c, v in list(numeric.items())[:6]
        )
        text = f"Apply '{fert}' fertilizer when: {details}."
        kws = _keywords(text, extra=[str(fert).lower(), "fertilizer", "npk", "soil", "deficiency"])
        chunks.append({"text": text, "keywords": kws})

    return _save("fertilizer_kaggle",
                 "Fertilizer Recommendation Guide (Kaggle)",
                 chunks, "fertilizer_kaggle.json")


def kaggle_crop_yield() -> int:
    print("\n[Kaggle] Crop Yield Dataset")
    slugs = [
        "patelris/crop-yield-prediction-dataset",
        "akshatgupta7/crop-yield-in-indian-states-dataset",
        "jmoldon/farmeasy-crop-recommendation",
    ]
    folder = None
    for slug in slugs:
        folder = _kaggle_download(slug, "yield")
        if folder:
            break
    if not folder:
        return 0

    import pandas as pd
    df = _kaggle_first_csv(folder)
    if df is None:
        return 0

    crop_col = next((c for c in df.columns if "crop" in c.lower()), None)
    yield_col = next((c for c in df.columns if "yield" in c.lower() or "production" in c.lower()), None)
    area_col = next((c for c in df.columns if "state" in c.lower() or "district" in c.lower() or "area" in c.lower()), None)

    chunks = []
    if crop_col and yield_col:
        for crop, grp in df.groupby(crop_col):
            text = (f"{crop} yield: average {float(grp[yield_col].mean()):.1f}, "
                    f"range {float(grp[yield_col].min()):.1f}–{float(grp[yield_col].max()):.1f} "
                    f"metric tons/hectare.")
            if area_col:
                top = grp.nlargest(3, yield_col)[area_col].tolist()
                text += f" High-yield regions: {', '.join(str(r) for r in top[:3])}."
            kws = _keywords(text, extra=[str(crop).lower(), "yield", "harvest", "production"])
            chunks.append({"text": text, "keywords": kws})

    return _save("crop_yield_kaggle",
                 "Crop Yield Statistics (Kaggle)",
                 chunks, "crop_yield_kaggle.json")


def kaggle_plant_disease() -> int:
    print("\n[Kaggle] Plant Disease Dataset")
    slugs = [
        "emmarex/plantdisease",
        "nirmalsankalana/crop-plant-disease-dataset",
        "mexwell/crop-disease",
    ]
    folder = None
    for slug in slugs:
        folder = _kaggle_download(slug, "plant_disease")
        if folder:
            break
    if not folder:
        return 0

    import pandas as pd
    df = _kaggle_first_csv(folder)
    if df is None:
        return 0

    text_cols = [c for c in df.columns if df[c].dtype == object]
    chunks = []
    for _, row in df.iterrows():
        text = " ".join(_clean(str(row[c])) for c in text_cols if pd.notna(row[c]) and len(str(row[c])) > 3)
        if len(text) < 40:
            continue
        for chunk in _chunk_text(text):
            kws = _keywords(chunk, extra=["disease", "plant", "crop", "symptoms", "treatment"])
            chunks.append({"text": chunk, "keywords": kws})

    return _save("plant_disease_kaggle",
                 "Plant Disease Database (Kaggle)",
                 chunks, "plant_disease_kaggle.json")


def kaggle_soil_types() -> int:
    print("\n[Kaggle] Soil Types & Properties")
    slugs = [
        "prasadsawant55/soil-types",
        "vikasukani/soil-types-data",
        "agileteam/soil-properties",
    ]
    folder = None
    for slug in slugs:
        folder = _kaggle_download(slug, "soil")
        if folder:
            break
    if not folder:
        return 0

    import pandas as pd
    df = _kaggle_first_csv(folder)
    if df is None:
        return 0

    text_cols = [c for c in df.columns if df[c].dtype == object]
    chunks = []
    for _, row in df.iterrows():
        parts = [f"{c}: {_clean(str(row[c]))}" for c in df.columns if pd.notna(row[c])]
        text = ". ".join(parts)
        if len(text) < 30:
            continue
        for chunk in _chunk_text(text):
            kws = _keywords(chunk, extra=["soil", "type", "texture", "clay", "loam"])
            chunks.append({"text": chunk, "keywords": kws})

    return _save("soil_types_kaggle",
                 "Soil Types & Properties (Kaggle)",
                 chunks, "soil_types_kaggle.json")


def kaggle_weather_crops() -> int:
    print("\n[Kaggle] Weather & Crop Relationships")
    slugs = [
        "rishavgarg10/weather-and-crop-recommendation",
        "sumitrodatta/indian-agriculture-data",
        "nehaprabhavalkar/av-healthcare-analytics-ii",
    ]
    folder = None
    for slug in slugs:
        folder = _kaggle_download(slug, "weather_crops")
        if folder:
            break
    if not folder:
        return 0

    import pandas as pd
    df = _kaggle_first_csv(folder)
    if df is None:
        return 0

    chunks = []
    for _, row in df.iterrows():
        parts = [f"{c}: {_clean(str(row[c]))}" for c in df.columns if pd.notna(row[c])]
        text = ". ".join(parts)
        if len(text) < 30:
            continue
        for chunk in _chunk_text(text):
            kws = _keywords(chunk, extra=["weather", "climate", "temperature", "rainfall", "crop"])
            chunks.append({"text": chunk, "keywords": kws})

    return _save("weather_crops_kaggle",
                 "Weather-Crop Relationships (Kaggle)",
                 chunks, "weather_crops_kaggle.json")


def kaggle_pesticide_usage() -> int:
    print("\n[Kaggle] Pesticide & Pest Management")
    slugs = [
        "unitednations/global-food-agriculture-statistics",
        "imtkaggle/pesticides-on-crops-worldwide",
        "patelris/crop-yield-prediction-dataset",
    ]
    folder = None
    for slug in slugs:
        folder = _kaggle_download(slug, "pesticide")
        if folder:
            break
    if not folder:
        return 0

    import pandas as pd
    df = _kaggle_first_csv(folder)
    if df is None:
        return 0

    crop_col = next((c for c in df.columns if "crop" in c.lower() or "item" in c.lower()), None)
    chunks = []
    for _, row in df.iterrows():
        parts = [f"{c}: {_clean(str(row[c]))}" for c in df.columns if pd.notna(row[c]) and str(row[c]).strip()]
        text = ". ".join(parts[:8])
        if len(text) < 40:
            continue
        for chunk in _chunk_text(text):
            kws = _keywords(chunk, extra=["pesticide", "pest", "insect", "crop", "protection"])
            chunks.append({"text": chunk, "keywords": kws})

    return _save("pesticide_kaggle",
                 "Pesticide & Crop Protection Data (Kaggle)",
                 chunks, "pesticide_kaggle.json")


# ─── Curated Fallback Knowledge ────────────────────────────────────────────────
# High-quality hand-crafted chunks added regardless of API availability.

CURATED_CHUNKS = [
    # ── Crop diseases ──────────────────────────────────────────────────────────
    {
        "text": (
            "Rice blast (Magnaporthe oryzae) causes diamond-shaped lesions on leaves and stem rot. "
            "It spreads rapidly in humid conditions (>90% RH) and temperatures 24–28°C. "
            "Management: use resistant varieties (IR-64, Swarna), apply Tricyclazole 75 WP at 0.6 g/L "
            "or Isoprothiolane 40 EC at 1.5 mL/L at first sign."
        ),
        "keywords": ["rice", "blast", "magnaporthe", "lesion", "tricyclazole", "disease", "fungal", "humidity"],
    },
    {
        "text": (
            "Powdery mildew on wheat and barley shows as white powdery patches on leaves and stems. "
            "Favoured by cool temperatures 15–22°C and moderate humidity. "
            "Control: spray Propiconazole 25 EC at 0.1% or Tebuconazole 250 EW at 1 mL/L. "
            "Crop rotation and removing infected debris reduces inoculum."
        ),
        "keywords": ["wheat", "barley", "powdery", "mildew", "propiconazole", "fungus", "disease", "spore"],
    },
    {
        "text": (
            "Cotton bollworm (Helicoverpa armigera) is India's most destructive pest, damaging flowers "
            "and bolls. Economic threshold: 1 larva per plant or 5–8% damaged squares. "
            "Management: pheromone traps (1/ha), spray Spinosad 45 SC 0.3 mL/L or Emamectin 5 SG 0.4 g/L. "
            "Bt cotton varieties reduce infestation by 70–80%."
        ),
        "keywords": ["cotton", "bollworm", "helicoverpa", "pest", "spinosad", "bt", "pheromone", "boll"],
    },
    {
        "text": (
            "Tomato early blight (Alternaria solani) causes dark concentric ring spots on lower leaves. "
            "Spreads in warm (24–29°C), wet weather. Apply Mancozeb 75 WP at 2.5 g/L or "
            "Chlorothalonil 75 WP at 2 g/L every 7–10 days. Remove infected leaves promptly."
        ),
        "keywords": ["tomato", "blight", "alternaria", "mancozeb", "fungal", "disease", "leaf", "spot"],
    },
    # ── Soil & Fertiliser ─────────────────────────────────────────────────────
    {
        "text": (
            "Black cotton soil (Vertisol) swells when wet and cracks when dry. "
            "It retains moisture well, ideal for cotton, soybean, sorghum. "
            "pH typically 7.5–8.5. Needs gypsum application (100–200 kg/ha) to correct alkalinity. "
            "Avoid waterlogging; ridge-and-furrow planting improves drainage."
        ),
        "keywords": ["black", "cotton", "vertisol", "soil", "gypsum", "alkaline", "drainage", "crack"],
    },
    {
        "text": (
            "Red laterite soils are acidic (pH 5–6.5), low in nitrogen and phosphorus but rich in iron. "
            "Found in peninsular India (Tamil Nadu, Kerala, Karnataka). "
            "Suitable for cashew, groundnut, mango, tapioca. "
            "Apply lime (500–1000 kg/ha) to raise pH, and compost to improve fertility."
        ),
        "keywords": ["red", "laterite", "acidic", "soil", "lime", "groundnut", "cashew", "iron"],
    },
    {
        "text": (
            "Urea (46% N) is the most widely used nitrogen fertiliser. "
            "Apply in split doses: 1/3 at sowing, 1/3 at tillering, 1/3 at panicle initiation for rice. "
            "Use neem-coated urea to reduce volatilisation loss by 10–15%. "
            "Excess urea causes lodging and increases susceptibility to blast."
        ),
        "keywords": ["urea", "nitrogen", "fertilizer", "neem", "coated", "split", "dose", "volatilisation"],
    },
    {
        "text": (
            "Soil organic carbon (SOC) above 0.5% improves water retention, structure, and microbial activity. "
            "Increase SOC by incorporating green manure (Dhaincha, Sunhemp), crop residues, "
            "farmyard manure (5–10 t/ha/year), and adopting zero-tillage. "
            "Target SOC of 0.75–1.0% for most Indian agricultural soils."
        ),
        "keywords": ["organic", "carbon", "soc", "compost", "manure", "microbial", "soil", "health"],
    },
    # ── Irrigation ────────────────────────────────────────────────────────────
    {
        "text": (
            "Drip irrigation reduces water use by 30–50% compared to flood irrigation. "
            "Ideal for sugarcane, vegetables, orchards. "
            "Operates at low pressure (1–2 bar) delivering water directly to root zone. "
            "Fertigation through drip increases fertiliser efficiency by 25–30%. "
            "Government subsidy available under PM-Krishi Sinchai Yojana."
        ),
        "keywords": ["drip", "irrigation", "water", "fertigation", "sugarcane", "efficiency", "subsidy"],
    },
    {
        "text": (
            "Sprinkler irrigation is suitable for wheat, mustard, groundnut, and vegetables on undulating land. "
            "Water saving of 20–35% vs flood. "
            "Install during early morning or evening to minimise evaporation. "
            "Avoid during high winds (>15 km/h) for uniform distribution."
        ),
        "keywords": ["sprinkler", "irrigation", "wheat", "mustard", "groundnut", "water", "saving"],
    },
    # ── Market & Schemes ──────────────────────────────────────────────────────
    {
        "text": (
            "Pradhan Mantri Fasal Bima Yojana (PMFBY) provides crop insurance at 2% premium for kharif "
            "and 1.5% for rabi crops. Claims cover losses from drought, flood, pest, and post-harvest damage. "
            "Enrol through Common Service Centres (CSC) or bank branches before the notified date. "
            "Aadhaar, bank passbook, and land records required."
        ),
        "keywords": ["pmfby", "fasal", "bima", "insurance", "premium", "kharif", "rabi", "scheme", "government"],
    },
    {
        "text": (
            "e-NAM (National Agriculture Market) is an online trading platform linking 1000+ APMCs. "
            "Farmers can sell directly to buyers across India, getting better price discovery. "
            "Register at enam.gov.in with Aadhaar and bank details. "
            "Charges are lower than traditional mandis."
        ),
        "keywords": ["enam", "mandi", "price", "market", "apmc", "online", "trade", "farmer"],
    },
    {
        "text": (
            "Minimum Support Price (MSP) for major kharif 2024 crops: "
            "Paddy ₹2300/quintal, Maize ₹2090/quintal, Cotton (medium staple) ₹7121/quintal, "
            "Groundnut ₹6783/quintal, Soybean ₹4892/quintal. "
            "Procurement through FCI and state agencies at notified purchase centres."
        ),
        "keywords": ["msp", "minimum", "support", "price", "paddy", "maize", "cotton", "groundnut", "kharif"],
    },
    # ── Pest Management ───────────────────────────────────────────────────────
    {
        "text": (
            "Integrated Pest Management (IPM) combines biological, cultural, and chemical methods. "
            "Steps: (1) regular scouting to reach economic threshold, (2) use bioagents "
            "(Trichogramma cards for stem borer), (3) sticky traps for whitefly and thrips, "
            "(4) chemical sprays only as last resort. Reduces pesticide cost by 40–60%."
        ),
        "keywords": ["ipm", "integrated", "pest", "management", "trichogramma", "bioagent", "scouting"],
    },
    {
        "text": (
            "Yellow sticky traps (25/ha) monitor and reduce whitefly, aphid, and leafhopper populations. "
            "Blue traps attract thrips. Pheromone traps (Helilure) for bollworm monitoring. "
            "Replace traps every 15 days. Record counts to decide spray timing."
        ),
        "keywords": ["trap", "sticky", "yellow", "whitefly", "aphid", "pheromone", "monitor", "pest"],
    },
    # ── Seasonal Calendar ─────────────────────────────────────────────────────
    {
        "text": (
            "Kharif season (June–October): sow after first monsoon rain (100–150 mm). "
            "Major crops: rice, maize, sorghum, cotton, soybean, groundnut, sugarcane. "
            "Land preparation: plough 2–3 times; puddling for transplanted rice. "
            "Harvest October–November. Sell before peak arrivals to get better prices."
        ),
        "keywords": ["kharif", "monsoon", "sowing", "rice", "maize", "sorghum", "season", "harvest"],
    },
    {
        "text": (
            "Rabi season (October–March): sow after monsoon retreat when soil temperature falls below 25°C. "
            "Major crops: wheat, mustard, chickpea, lentil, potato, sunflower. "
            "Irrigation crucial: wheat needs 4–5 irrigations; mustard 1–2. "
            "Harvest March–April. Store in hermetic bags to avoid insect damage."
        ),
        "keywords": ["rabi", "wheat", "mustard", "chickpea", "winter", "season", "irrigation", "harvest"],
    },
    # ── Seed & Variety ────────────────────────────────────────────────────────
    {
        "text": (
            "Hybrid seeds give 20–30% higher yield than open-pollinated varieties but must be repurchased each year. "
            "High-yielding wheat varieties for India: HD-3086 (north), GW-496 (Gujarat), "
            "PBW-725 (Punjab). For rice: Swarna, MTU-7029 (Samba Mahsuri), Pusa Basmati 1121 (export)."
        ),
        "keywords": ["hybrid", "seed", "variety", "wheat", "rice", "yield", "hd3086", "swarna", "basmati"],
    },
    {
        "text": (
            "Seed treatment before sowing protects against soil-borne pathogens and early-season pests. "
            "Treat with Carbendazim 2 g/kg + Thiram 3 g/kg for fungal protection. "
            "For nematodes, use Carbofuran 3G in seed furrow at 1 kg/ha. "
            "Bio-seed treatment with Trichoderma viride 4 g/kg improves germination and root health."
        ),
        "keywords": ["seed", "treatment", "carbendazim", "thiram", "trichoderma", "nematode", "germination"],
    },
    # ── Post-harvest ─────────────────────────────────────────────────────────
    {
        "text": (
            "Grain moisture at harvest: wheat 12–14%, rice 14–17%, maize 18–22%. "
            "Dry to safe storage moisture (wheat <12%, rice <14%) to prevent mould. "
            "Use moisture meters before bagging. Store in HDPE woven bags or hermetic bags. "
            "Fumigate with Aluminium Phosphide 3 g/tonne for long-term storage."
        ),
        "keywords": ["moisture", "storage", "grain", "wheat", "rice", "maize", "hermetic", "fumigation"],
    },
    {
        "text": (
            "Cold storage extends shelf life of potatoes (6–9 months at 4°C), "
            "apples (4–6 months at 1–4°C), and grapes (2–3 months at 0°C). "
            "Pre-cooling within 6 hours of harvest reduces field heat. "
            "Government subsidises cold chain under Pradhan Mantri Kisan Sampada Yojana."
        ),
        "keywords": ["cold", "storage", "potato", "apple", "grape", "shelf", "life", "postharvest"],
    },
]


def save_curated_knowledge() -> int:
    print("\n[Curated] Built-in Expert Knowledge")
    return _save(
        "curated_expert_knowledge",
        "Expert Farming Knowledge (Curated)",
        CURATED_CHUNKS,
        "curated_expert_knowledge.json",
    )


# ─── Index Rebuild ─────────────────────────────────────────────────────────────

def rebuild_index() -> None:
    index_entries = []
    total = 0
    for jf in sorted(DATASETS_DIR.glob("*.json")):
        if jf.name in ("_built_index.json", "manifest.json"):
            continue
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
            n = len(data.get("chunks", []))
            index_entries.append({"id": data.get("id", jf.stem),
                                   "name": data.get("name", jf.stem),
                                   "chunks": n, "file": jf.name})
            total += n
        except Exception as e:
            print(f"  [warn] Could not index {jf.name}: {e}")
    index = {"datasets": index_entries, "total_chunks": total}
    try:
        (DATASETS_DIR / "_built_index.json").write_text(
            json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print("\n" + "=" * 60)
        print(f"  Dataset Index Rebuilt")
        print(f"  {len(index_entries)} datasets, {total} total chunks")
        print("=" * 60)
        for e in index_entries:
            print(f"  {e['file']:<45} {e['chunks']:>4} chunks")
    except Exception as e:
        print(f"  [error] Failed to rebuild index: {e}")


# ─── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("  Crop Bot - Farming Dataset Trainer")
    print("  Fetching data from HuggingFace & Kaggle")
    print("=" * 60)

    # Check what we actually need before installing
    print("\n[setup] Checking requirements...")
    has_kaggle = kaggle_available()

    # Install Python deps for data loading (not needed in production)
    print("[setup] Installing data-loading packages...")
    packages = ["numpy"]  # Core requirement
    if not SKIP_HUGGINGFACE:
        packages.extend(["datasets", "pandas", "huggingface_hub"])
    if has_kaggle:
        packages.append("kaggle")
    _pip_install(*packages)

    total = 0

    # ── Always-available curated knowledge ──────────────────────────────────
    print("\n[curated] Loading built-in expert knowledge...")
    total += save_curated_knowledge()

    # ── HuggingFace ─────────────────────────────────────────────────────────
    if not SKIP_HUGGINGFACE:
        print("\n[huggingface] Downloading datasets...")
        print("   (Set SKIP_HF=1 environment variable to skip)")
        total += hf_crop_recommendation()
        total += hf_plant_diseases()
        total += hf_agricultural_qa()
        total += hf_soil_health()
        total += hf_fertilizer_data()
        total += hf_crop_diseases_india()
    else:
        print("\n[huggingface] Skipped (SKIP_HF=1)")

    # ── Kaggle ───────────────────────────────────────────────────────────────
    if has_kaggle:
        print("\n[kaggle] Downloading datasets...")
        total += kaggle_crop_recommendation()
        total += kaggle_fertilizer()
        total += kaggle_crop_yield()
        total += kaggle_plant_disease()
        total += kaggle_soil_types()
        total += kaggle_weather_crops()
        total += kaggle_pesticide_usage()

    # ── Cleanup temp files ───────────────────────────────────────────────────
    if TEMP_DIR.exists():
        try:
            shutil.rmtree(TEMP_DIR)
        except Exception as e:
            print(f"  [warn] Could not clean temp dir: {e}")

    # ── Rebuild RAG index ────────────────────────────────────────────────────
    rebuild_index()

    print(f"\n[done] Training complete!")
    print(f"       {total} knowledge chunks added to Crop Bot")
    print(f"       Next: python train_datasets.py")
    print(f"       Then: restart server.py\n")


if __name__ == "__main__":
    main()
