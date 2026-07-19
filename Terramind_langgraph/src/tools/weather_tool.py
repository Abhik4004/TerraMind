"""
Weather + air-quality tools using Open-Meteo — free, open data, NO API key.

Open-Meteo (https://open-meteo.com) is a free, open-source weather API built on
national weather-service data. No registration or key is required for
non-commercial use.

Endpoints used:
  /v1/forecast                       — current conditions + daily min/max
  /v1/forecast?past_days=N           — real recent/historical weather
  air-quality-api /v1/air-quality    — PM2.5, PM10, ozone, NO2, SO2, CO, AQI

Results are cached via cache_manager to be a good API citizen.
"""
import time
import httpx
from typing import Dict, Any, List, Tuple
from src.config.settings import settings
from src.utils.cache_manager import cache_manager

_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
_AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
_TIMEOUT = settings.TOOL_TIMEOUT

# WMO weather interpretation codes -> human-readable description.
_WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    56: "Light freezing drizzle", 57: "Dense freezing drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    66: "Light freezing rain", 67: "Heavy freezing rain",
    71: "Slight snowfall", 73: "Moderate snowfall", 75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
}


class WeatherToolError(Exception):
    pass


def _describe(code) -> str:
    try:
        return _WMO_CODES.get(int(code), "Unknown")
    except (TypeError, ValueError):
        return "Unknown"


def _get(url: str, params: dict, retries: int = 2) -> dict:
    """GET with a couple of retries — public APIs occasionally return transient 5xx."""
    last_err = None
    for attempt in range(retries + 1):
        try:
            resp = httpx.get(url, params=params, timeout=_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            last_err = WeatherToolError(
                f"Open-Meteo API error {e.response.status_code}: {e.response.text[:200]}"
            )
            # Only retry on server-side (5xx) errors; 4xx won't fix itself.
            if e.response.status_code < 500:
                break
        except Exception as e:
            last_err = WeatherToolError(f"Open-Meteo request failed: {e}")
        if attempt < retries:
            time.sleep(0.8 * (attempt + 1))
    raise last_err


def get_weather_data(lat: float, lon: float) -> Dict[str, Any]:
    """
    Fetch current weather conditions for the given coordinates via Open-Meteo.

    Returns a flat dict with temperature, humidity, wind, etc.
    Results are cached to avoid excessive API calls.
    """
    cache_key = cache_manager._generate_cache_key(
        {"tool": "get_weather_data", "lat": round(lat, 3), "lon": round(lon, 3)}
    )
    cached = cache_manager.get(cache_key, cache_type="tool")
    if cached:
        cached["from_cache"] = True
        return cached

    d = _get(_FORECAST_URL, {
        "latitude": lat,
        "longitude": lon,
        "current": (
            "temperature_2m,relative_humidity_2m,apparent_temperature,"
            "precipitation,weather_code,cloud_cover,pressure_msl,"
            "wind_speed_10m,wind_direction_10m"
        ),
        "daily": "temperature_2m_max,temperature_2m_min",
        "wind_speed_unit": "ms",
        "timezone": "auto",
        "forecast_days": 1,
    })

    cur = d.get("current", {})
    daily = d.get("daily", {})

    def _first(key):
        vals = daily.get(key)
        return vals[0] if isinstance(vals, list) and vals else None

    result = {
        "location": d.get("timezone", f"{lat:.3f}, {lon:.3f}"),
        "latitude": d.get("latitude", lat),
        "longitude": d.get("longitude", lon),
        "temp_c": cur.get("temperature_2m"),
        "feels_like_c": cur.get("apparent_temperature"),
        "temp_min_c": _first("temperature_2m_min"),
        "temp_max_c": _first("temperature_2m_max"),
        "humidity_pct": cur.get("relative_humidity_2m"),
        "pressure_hpa": cur.get("pressure_msl"),
        "wind_speed_ms": cur.get("wind_speed_10m"),
        "wind_deg": cur.get("wind_direction_10m"),
        "clouds_pct": cur.get("cloud_cover"),
        "precipitation_mm": cur.get("precipitation"),
        "description": _describe(cur.get("weather_code")),
        "observed_at": cur.get("time"),
        "source": "Open-Meteo",
        "from_cache": False,
    }
    cache_manager.set(cache_key, result, cache_type="tool")
    return result


def get_recent_weather_data(lat: float, lon: float, days: int = 5) -> Dict[str, Any]:
    """
    Fetch REAL recent/historical weather for the past `days` via Open-Meteo.

    Unlike the previous provider's free tier (which could only forecast),
    Open-Meteo's `past_days` parameter returns genuine observed data. Hourly
    readings are aggregated into daily summaries.
    """
    days = max(1, min(days, 92))  # Open-Meteo allows up to 92 past days
    cache_key = cache_manager._generate_cache_key(
        {"tool": "get_recent_weather_data", "lat": round(lat, 3), "lon": round(lon, 3), "days": days}
    )
    cached = cache_manager.get(cache_key, cache_type="tool")
    if cached:
        cached["from_cache"] = True
        return cached

    d = _get(_FORECAST_URL, {
        "latitude": lat,
        "longitude": lon,
        "daily": (
            "temperature_2m_max,temperature_2m_min,precipitation_sum,"
            "wind_speed_10m_max,weather_code"
        ),
        "wind_speed_unit": "ms",
        "past_days": days,
        "forecast_days": 1,
        "timezone": "auto",
    })

    daily = d.get("daily", {})
    dates = daily.get("time", []) or []
    summaries = []
    for i, date in enumerate(dates):
        def _at(key):
            vals = daily.get(key) or []
            return vals[i] if i < len(vals) else None

        summaries.append({
            "date": date,
            "temp_min_c": _at("temperature_2m_min"),
            "temp_max_c": _at("temperature_2m_max"),
            "precipitation_mm": _at("precipitation_sum"),
            "wind_speed_max_ms": _at("wind_speed_10m_max"),
            "description": _describe(_at("weather_code")),
        })

    result = {
        "location": d.get("timezone", f"{lat:.3f}, {lon:.3f}"),
        "latitude": d.get("latitude", lat),
        "longitude": d.get("longitude", lon),
        "days": days,
        "daily_summaries": summaries,
        "source": "Open-Meteo",
        "from_cache": False,
    }
    cache_manager.set(cache_key, result, cache_type="tool")
    return result


def get_air_quality_data(lat: float, lon: float) -> Dict[str, Any]:
    """
    Fetch current air-quality / pollution data via Open-Meteo Air Quality API.

    Returns AQI (US and European) plus pollutant concentrations. No API key.
    """
    cache_key = cache_manager._generate_cache_key(
        {"tool": "get_air_quality_data", "lat": round(lat, 3), "lon": round(lon, 3)}
    )
    cached = cache_manager.get(cache_key, cache_type="tool")
    if cached:
        cached["from_cache"] = True
        return cached

    d = _get(_AIR_QUALITY_URL, {
        "latitude": lat,
        "longitude": lon,
        "current": (
            "pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,"
            "sulphur_dioxide,ozone,us_aqi,european_aqi"
        ),
        "timezone": "auto",
    })

    cur = d.get("current", {})
    result = {
        "us_aqi": cur.get("us_aqi"),
        "european_aqi": cur.get("european_aqi"),
        "components_ug_m3": {
            "pm2_5": cur.get("pm2_5"),
            "pm10": cur.get("pm10"),
            "carbon_monoxide": cur.get("carbon_monoxide"),
            "nitrogen_dioxide": cur.get("nitrogen_dioxide"),
            "sulphur_dioxide": cur.get("sulphur_dioxide"),
            "ozone": cur.get("ozone"),
        },
        "observed_at": cur.get("time"),
        "source": "Open-Meteo Air Quality",
        "from_cache": False,
    }
    cache_manager.set(cache_key, result, cache_type="tool")
    return result


def get_weather_comparison(locations: List[Tuple[float, float]]) -> Dict[str, Any]:
    """
    Fetch and compare current weather for multiple (lat, lon) pairs.
    """
    comparison = {}
    for idx, (lat, lon) in enumerate(locations):
        label = f"location_{idx + 1}"
        try:
            comparison[label] = get_weather_data(lat, lon)
        except WeatherToolError as e:
            comparison[label] = {"error": str(e)}
    return {"comparison": comparison, "location_count": len(locations)}
