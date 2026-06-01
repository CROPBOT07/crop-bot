"""Load farming JSON datasets and retrieve chunks for RAG-style prompts (keyword + word overlap)."""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

DATASETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datasets")

# Max characters injected into the system prompt (keep room for the answer)
MAX_CONTEXT_CHARS = 3500
TOP_CHUNKS = 7  # increased from 5 for better coverage
MIN_WORD_LEN = 2

# Common words that add noise — skip boosting these
_STOPWORDS = {
    'the', 'is', 'in', 'it', 'of', 'to', 'and', 'a', 'an', 'for',
    'on', 'at', 'by', 'be', 'as', 'or', 'do', 'my', 'me', 'we',
    'how', 'what', 'when', 'why', 'can', 'i', 'you', 'are', 'was',
}


def _tokenize(text: str) -> set:
    words = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return {w for w in words if len(w) >= MIN_WORD_LEN}


def _bigrams(tokens: set) -> set:
    lst = sorted(tokens)
    return {f"{lst[i]}_{lst[i+1]}" for i in range(len(lst) - 1)}


def _chunk_score(question_tokens: set, keywords: List[str], text: str) -> float:
    # Remove stopwords from question tokens for keyword matching
    q_content = {t for t in question_tokens if t not in _STOPWORDS}

    kw_tokens = _tokenize(" ".join(keywords)) if keywords else set()
    text_tokens = _tokenize(text)

    overlap_q_kw = len(q_content & kw_tokens)
    overlap_q_text = len(q_content & text_tokens)

    # Bigram bonus — phrase-level matching scores higher
    q_bigrams = _bigrams(q_content)
    text_bigrams = _bigrams(text_tokens)
    bigram_bonus = len(q_bigrams & text_bigrams) * 2.0

    # Keyword density bonus — reward chunks where matched keywords are a large fraction
    kw_density = (overlap_q_kw / max(len(kw_tokens), 1)) * 1.5

    return (
        overlap_q_kw * 3.0
        + overlap_q_text * 1.0
        + bigram_bonus
        + kw_density
        + (0.5 if overlap_q_kw else 0.0)
    )


def load_dataset_file(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[dataset_loader] Could not load dataset {path}: {e}")
        return None
    if not isinstance(data, dict):
        return None
    chunks = data.get("chunks")
    if not isinstance(chunks, list) or not chunks:
        return None
    ds_id = data.get("id") or os.path.splitext(os.path.basename(path))[0]
    name = data.get("name") or ds_id
    normalized = []
    for c in chunks:
        if not isinstance(c, dict):
            continue
        text = (c.get("text") or "").strip()
        if not text:
            continue
        kws = c.get("keywords") or []
        if isinstance(kws, str):
            kws = [kws]
        if not isinstance(kws, list):
            kws = []
        kws = [str(x).strip() for x in kws if str(x).strip()]
        normalized.append({"text": text, "keywords": kws})
    if not normalized:
        return None
    return {"id": ds_id, "name": name, "chunks": normalized, "source_file": os.path.basename(path)}


def load_all_datasets(datasets_dir: str = DATASETS_DIR) -> Dict[str, Dict[str, Any]]:
    """Load every *.json in datasets/ except index/build artifacts."""
    out: Dict[str, Dict[str, Any]] = {}
    if not os.path.isdir(datasets_dir):
        return out
    skip = {"manifest.json", "_built_index.json"}
    for name in sorted(os.listdir(datasets_dir)):
        if not name.endswith(".json") or name in skip:
            continue
        path = os.path.join(datasets_dir, name)
        if not os.path.isfile(path):
            continue
        ds = load_dataset_file(path)
        if ds:
            out[ds["id"]] = ds
    return out


def retrieve_chunks(
    question: str,
    datasets: Dict[str, Dict[str, Any]],
    scope: str = "all",
) -> List[Tuple[str, str, float]]:
    """
    Return list of (dataset_id, chunk_text, score) sorted by score descending.
    scope: 'all' or a specific dataset id.
    """
    q_tokens = _tokenize(question)
    if not q_tokens:
        return []

    candidates: List[Tuple[str, str, float]] = []
    for ds_id, ds in datasets.items():
        if scope != "all" and ds_id != scope:
            continue
        for ch in ds["chunks"]:
            score = _chunk_score(q_tokens, ch["keywords"], ch["text"])
            if score > 0:
                candidates.append((ds_id, ch["text"], score))

    candidates.sort(key=lambda x: x[2], reverse=True)
    return candidates


def build_context(
    question: str,
    datasets: Dict[str, Dict[str, Any]],
    scope: str = "all",
) -> str:
    """Build a single string of reference text for the system prompt."""
    ranked = retrieve_chunks(question, datasets, scope)
    if not ranked:
        return ""

    parts: List[str] = []
    total = 0
    seen = set()
    for ds_id, text, _ in ranked[: TOP_CHUNKS * 3]:
        key = (ds_id, text[:200])
        if key in seen:
            continue
        seen.add(key)
        label = datasets.get(ds_id, {}).get("name", ds_id)
        block = f"[{label}]\n{text.strip()}"
        if total + len(block) > MAX_CONTEXT_CHARS:
            break
        parts.append(block)
        total += len(block)
        if len(parts) >= TOP_CHUNKS:
            break

    return "\n\n---\n\n".join(parts)


def list_dataset_metadata(datasets: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for ds_id, ds in sorted(datasets.items(), key=lambda x: x[0]):
        n = len(ds.get("chunks", []))
        rows.append(
            {
                "id": ds_id,
                "name": ds.get("name", ds_id),
                "chunks": n,
                "file": ds.get("source_file", ""),
            }
        )
    return rows
