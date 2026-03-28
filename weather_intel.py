"""Hyperlocal weather via Open-Meteo (no API key) + simple rule-based farm alerts."""
from __future__ import annotations

import requests
from typing import Any, Dict, List, Optional

OPEN_METEO = "https://api.open-meteo.com/v1/forecast"


def fetch_weather(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """Return structured weather + daily slice for India-friendly timezone."""
    try:
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code",
            "hourly": "precipitation_probability,precipitation",
            "daily": "weather_code,precipitation_sum,precipitation_probability_max",
            "forecast_days": 3,
            "timezone": "auto",
        }
        r = requests.get(OPEN_METEO, params=params, timeout=15)
        if r.status_code != 200:
            return None
        return r.json()
    except (requests.RequestException, ValueError):
        return None


def _max_precip_prob_next_hours(hourly: Dict[str, Any], hours: int = 24) -> Optional[float]:
    probs = hourly.get("precipitation_probability") or []
    if not probs:
        return None
    chunk = probs[:hours]
    return max(chunk) if chunk else None


def build_alerts(data: Dict[str, Any]) -> List[str]:
    """Rule-based proactive tips (not a substitute for IMD official bulletins)."""
    alerts: List[str] = []
    cur = data.get("current") or {}
    daily = data.get("daily") or {}
    hourly = data.get("hourly") or {}

    temp = cur.get("temperature_2m")
    rh = cur.get("relative_humidity_2m")

    if temp is not None and temp > 35:
        alerts.append(
            "Heat stress alert: temperature above 35°C — irrigate early morning, consider shade nets for sensitive crops."
        )

    if temp is not None and temp < 10:
        alerts.append(
            "Cold night risk: protect sensitive seedlings and young plants from chill damage."
        )

    if rh is not None and rh >= 80:
        alerts.append("High humidity - higher risk of fungal diseases; improve airflow and scout leaves.")

    # Tomorrow = index 1 in daily arrays
    times = daily.get("time") or []
    prec_max = daily.get("precipitation_sum") or []
    pprob = daily.get("precipitation_probability_max") or []

    if len(times) > 1 and len(prec_max) > 1:
        tomorrow_rain = float(prec_max[1] or 0)
        tomorrow_prob = pprob[1] if len(pprob) > 1 else None
        if tomorrow_rain >= 20:
            alerts.append(
                f"Heavy rain forecast tomorrow (~{round(tomorrow_rain)}mm) — check field drainage and avoid spraying."
            )
        elif tomorrow_rain >= 3 or (tomorrow_prob is not None and tomorrow_prob >= 60):
            alerts.append("Rain expected tomorrow - consider delaying irrigation and plan spraying around dry windows.")

    mx = _max_precip_prob_next_hours(hourly, 12)
    if mx is not None and mx >= 70 and not any("Rain expected tomorrow" in a or "Heavy rain" in a for a in alerts):
        alerts.append("High chance of rain in the next 12 hours — protect hay / harvested grain from moisture.")

    if not alerts:
        alerts.append("No immediate weather red flags from these rules - still monitor local IMD forecasts.")

    return alerts


def summarize_for_prompt(data: Dict[str, Any], lat: float, lon: float) -> str:
    cur = data.get("current") or {}
    daily = data.get("daily") or {}
    hourly = data.get("hourly") or {}

    temp = cur.get("temperature_2m")
    rh = cur.get("relative_humidity_2m")
    wc = cur.get("weather_code")

    lines = [
        f"Approximate location context: lat {lat:.4f}, lon {lon:.4f} (weather grid from Open-Meteo, not official IMD).",
        f"Current: temperature ~{temp}°C, relative humidity ~{rh}% (weather code {wc}).",
    ]

    times = daily.get("time") or []
    prec_sum = daily.get("precipitation_sum") or []
    if len(times) > 1 and len(prec_sum) > 1:
        lines.append(
            f"Next day rainfall (model): ~{prec_sum[1]} mm on {times[1]} - use for irrigation timing hints only."
        )

    mx = _max_precip_prob_next_hours(hourly, 24)
    if mx is not None:
        lines.append(f"Max hourly rain probability in next 24h (model): ~{mx}%.")

    lines.append("Proactive alerts (rules): " + " | ".join(build_alerts(data)))
    return "\n".join(lines)
