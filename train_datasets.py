
import kagglehub

# Download latest version
path = kagglehub.dataset_download("midouazerty/work-for-parmavir")

print("Path to dataset files:", path)
import kagglehub

# Download latest version
path = kagglehub.dataset_download("tarundalal/dangerous-insects-dataset")

print("Path to dataset files:", path)
import kagglehub

# Download latest version
path = kagglehub.dataset_download("atharvasoundankar/smart-farming-sensor-data-for-yield-prediction")

print("Path to dataset files:", path)
import kagglehub

# Download latest version
path = kagglehub.dataset_download("japondo/corn-farming-data")

print("Path to dataset files:", path)
import kagglehub

# Download latest version
path = kagglehub.dataset_download("bhadramohit/agriculture-and-farming-dataset")

print("Path to dataset files:", path)
#!/usr/bin/env python3
"""
Validate farming JSON datasets and write a small index (metadata only).
Run after adding or editing files in datasets/:

    python train_datasets.py

This does not train an ML model — it checks schema and reports counts so you
can manage multiple curated datasets confidently.
"""
from __future__ import annotations

import json
import os
import sys

from dataset_loader import DATASETS_DIR, load_all_datasets, list_dataset_metadata


def main() -> int:
    if not os.path.isdir(DATASETS_DIR):
        print(f"[ERROR] Missing folder: {DATASETS_DIR}")
        print("   Create it and add *.json dataset files.")
        return 1

    datasets = load_all_datasets()
    if not datasets:
        print(f"⚠️  No valid datasets found in {DATASETS_DIR}")
        print("   Each file should be JSON with: id, name, chunks[].text, chunks[].keywords")
        return 1

    meta = list_dataset_metadata(datasets)
    total_chunks = sum(m["chunks"] for m in meta)

    index_path = os.path.join(DATASETS_DIR, "_built_index.json")
    payload = {
        "datasets": meta,
        "total_chunks": total_chunks,
        "datasets_dir": DATASETS_DIR,
    }
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print("[OK] Dataset training index (validation) complete\n")
    print(f"   Folder: {DATASETS_DIR}")
    print(f"   Datasets: {len(meta)}  |  Total chunks: {total_chunks}")
    print(f"   Written: {index_path}\n")
    for m in meta:
        print(f"   - {m['id']}: {m['name']} ({m['chunks']} chunks) [{m['file']}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
