"""Optional crop photo analysis via OpenAI vision (set OPENAI_API_KEY in .env)."""
from __future__ import annotations

import os
from typing import Optional

import requests


def analyze_crop_image(image_b64: str, mime: str = "image/jpeg") -> Optional[str]:
    """
    Returns a short agronomy-style text summary, or None if unavailable / error.
    """
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key or not image_b64:
        return None

    url = "https://api.openai.com/v1/chat/completions"
    prompt = (
        "You are an agricultural extension expert in India. "
        "Look at this crop/plant photo. Describe: (1) what you see, (2) possible disease, pest, or nutrient issues, "
        "(3) severity as low/medium/high urgency, (4) immediate safe steps and when to call a local expert. "
        "Use simple language. If the image is not a plant, say so briefly."
    )
    payload = {
        "model": "gpt-4o-mini",
        "max_tokens": 600,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{image_b64}"},
                    },
                ],
            }
        ],
    }
    try:
        r = requests.post(
            url,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
            timeout=90,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()
    except (requests.RequestException, KeyError, ValueError):
        return None
