# Crop Bot Farming Datasets Training Guide

## Overview

The `fetch_farming_datasets.py` script automatically downloads and integrates farming datasets from **HuggingFace** and **Kaggle** into your Crop Bot RAG system. It converts raw data into optimized JSON chunks that improve the AI assistant's farming advice accuracy.

## Features

✓ **Automatic dataset discovery** - Tries multiple dataset sources, falls back gracefully
✓ **Intelligent chunking** - Splits large documents into 800-char chunks with sentence boundaries
✓ **Smart deduplication** - Removes duplicate content across datasets
✓ **Keyword extraction** - Automatically tags chunks with relevant keywords for RAG retrieval
✓ **Unicode-safe output** - Works on Windows, Linux, macOS
✓ **Error resilient** - Continues on timeout/network errors, captures partial data
✓ **Fast curated knowledge** - 21 hand-crafted expert agricultural chunks included by default

## Datasets Included

### Built-in Curated Knowledge (21 chunks)
- **Crop Diseases**: Rice blast, powdery mildew, cotton bollworm, tomato blight
- **Soil & Fertilizer**: Black cotton soil, red laterite soil, urea application, organic carbon
- **Irrigation**: Drip irrigation, sprinkler systems, water efficiency
- **Government Schemes**: PMFBY, e-NAM, MSP
- **Pest Management**: IPM strategies, sticky traps, biological control
- **Seasonal Calendars**: Kharif and rabi crop planning
- **Seeds & Varieties**: Hybrid seeds, seed treatment, germination
- **Post-Harvest**: Grain moisture, storage, cold chains

### HuggingFace Datasets (auto-download)
1. **Crop Recommendation** - NPK requirements, temperature, humidity, rainfall for major crops
2. **Plant Disease Guide** - Symptoms, causes, and treatments for crop diseases
3. **Agricultural Q&A** - Knowledge base answers extracted from farming forums
4. **Soil Health** - Soil properties, classification, nutrient content
5. **Fertilizer Recommendation** - Optimal NPK levels by soil type
6. **Indian Crop Diseases** - Context-specific Indian agriculture data

### Kaggle Datasets (requires authentication)
1. **Crop Recommendation** - Growing conditions by crop type
2. **Fertilizer Recommendation** - Soil-based fertilizer selection
3. **Crop Yield** - Historical yield data by region and crop
4. **Plant Disease Database** - Comprehensive disease diagnostics
5. **Soil Types & Properties** - Detailed soil classification
6. **Weather-Crop Relationships** - Climate impact on crop selection
7. **Pesticide & Crop Protection** - Pest management strategies

## Quick Start

### 1. Run with Curated Knowledge Only (Fast)
```bash
SKIP_HF=1 python fetch_farming_datasets.py
```
Takes ~10 seconds. Creates `curated_expert_knowledge.json` with 21 expert chunks.

### 2. Run with HuggingFace Datasets (Recommended)
```bash
python fetch_farming_datasets.py
```
Takes ~2-5 minutes (depending on internet). Downloads 6 HuggingFace datasets if available.

### 3. Run with Full Kaggle Support (All Data)
First, set up Kaggle credentials:
```bash
# Go to https://www.kaggle.com/account
# Click "Create New API Token"
# Save kaggle.json to ~/.kaggle/kaggle.json (or C:\Users\YourName\.kaggle\kaggle.json on Windows)
```

Then run:
```bash
python fetch_farming_datasets.py
```

## Output Files

After running, check `datasets/` folder:

```
datasets/
├── _built_index.json                      # Auto-generated metadata index
├── curated_expert_knowledge.json          # 21 hand-crafted chunks
├── crop_recommendation_hf.json            # HF crop data (if downloaded)
├── plant_diseases_hf.json                 # HF disease guide
├── agricultural_qa_hf.json                # HF Q&A knowledge
├── soil_health_hf.json                    # HF soil data
├── fertilizer_recommendation_hf.json      # HF fertilizer guide
├── crop_diseases_india_hf.json            # HF Indian-specific data
├── crop_recommendation_kaggle.json        # Kaggle crop data (if available)
├── fertilizer_kaggle.json                 # Kaggle fertilizer data (if available)
├── crop_yield_kaggle.json                 # Kaggle yield statistics
├── plant_disease_kaggle.json              # Kaggle disease database
├── soil_types_kaggle.json                 # Kaggle soil classification
├── weather_crops_kaggle.json              # Kaggle climate-crop relationships
└── pesticide_kaggle.json                  # Kaggle pest protection
```

## Validation

After training, validate all datasets:
```bash
python train_datasets.py
```

This checks JSON schema, counts chunks, and builds metadata index.

## Integration with Crop Bot

The RAG system automatically loads all JSON files from `datasets/` folder when `server.py` starts. The `_built_index.json` provides metadata for the frontend `/datasets` endpoint.

When a farmer asks a question:
1. Question is tokenized
2. Keywords are matched against all dataset chunks
3. Top 5 most relevant chunks are retrieved
4. Chunks are injected into the system prompt
5. AI provider (DeepSeek, etc.) generates context-aware answer

## Performance

- **Chunk storage**: Each chunk ~500-800 chars, ~50KB per 100 chunks
- **Retrieval speed**: <10ms keyword matching on all datasets
- **Context injection**: ~3500 chars max per prompt (typically 3-5 chunks)
- **Total dataset payload**: With all HF+Kaggle datasets: ~50-100 MB disk, fits easily in RAM

## Troubleshooting

### HuggingFace datasets timeout or fail
Set a shorter timeout or skip HF:
```bash
SKIP_HF=1 python fetch_farming_datasets.py
```

### Kaggle authentication fails
- Verify `~/.kaggle/kaggle.json` exists and is readable
- Check JSON format is correct:
  ```json
  {
    "username": "your_kaggle_username",
    "key": "your_api_key"
  }
  ```

### Script hangs or crashes
- Check disk space (need ~500 MB for temp downloads)
- Verify network connectivity
- Run with `SKIP_HF=1` for minimal dependencies
- Check Python version ≥3.9

### Unicode/encoding errors on Windows
- Already fixed in latest version (force UTF-8 output)
- If still occurring, ensure Windows terminal encoding is UTF-8

## Data Quality Notes

- **Curated chunks**: Hand-reviewed, high-confidence agricultural advice
- **HuggingFace chunks**: Auto-converted from datasets, may need manual review
- **Kaggle chunks**: Variable quality, statistical data may be outdated
- **Deduplication**: Script removes exact duplicates, similar content is kept for diversity

## Next Steps

1. Run `fetch_farming_datasets.py` to populate datasets
2. Run `python train_datasets.py` to validate
3. Restart `server.py` to apply new knowledge
4. Test via `https://crop-bot.onrender.com` with farming questions

## Advanced Usage

### Custom Environment Variables
```bash
SKIP_HF=1              # Skip HuggingFace downloads
HF_TIMEOUT=120         # Increase HF timeout to 2 minutes
```

### Adding Custom Datasets

Create a JSON file in `datasets/` folder with format:
```json
{
  "id": "my_dataset",
  "name": "My Custom Farming Knowledge",
  "chunks": [
    {
      "text": "Detailed farming advice here...",
      "keywords": ["crop", "condition", "management"]
    }
  ]
}
```

Then run `python train_datasets.py` to rebuild index.

## Credits

- **Crop Bot** by Ayushmaan Singh Pundir (Age 12, India)
- **Datasets**: HuggingFace, Kaggle community contributors
- **RAG System**: Custom keyword-based retrieval with semantic scoring

---

**Last Updated**: 2026-03-29
**Script Version**: 2.0
