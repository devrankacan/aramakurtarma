import logging
from datetime import datetime, timedelta, timezone

import requests
from django.core.cache import cache

logger = logging.getLogger(__name__)

AFAD_API_URL = "https://deprem.afad.gov.tr/apiv2/event/filter"
CACHE_KEY = "afad_recent_earthquakes"
CACHE_TTL_SECONDS = 300


def fetch_recent_earthquakes(limit=15):
    """AFAD'ın resmi deprem API'sinden son depremleri çeker. Sonuç Redis'te
    kısa süre önbelleklenir; API'ye ulaşılamazsa boş liste döner (ana sayfayı
    çökertmez), şablon bu durumu ayrıca ele alır."""
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    now = datetime.now(timezone.utc)
    params = {
        "start": (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S"),
        "end": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "limit": limit,
        "orderby": "timedesc",
    }

    try:
        response = requests.get(AFAD_API_URL, params=params, timeout=5)
        response.raise_for_status()
        raw_events = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("AFAD deprem verisi alınamadı: %s", exc)
        return []

    earthquakes = []
    for item in raw_events[:limit]:
        magnitude = item.get("magnitude") or item.get("mw") or item.get("ml") or item.get("md")
        try:
            magnitude = round(float(magnitude), 1) if magnitude is not None else None
        except (TypeError, ValueError):
            magnitude = None
        earthquakes.append(
            {
                "location": item.get("location") or item.get("province") or "Bilinmiyor",
                "province": item.get("province"),
                "date": item.get("date"),
                "magnitude": magnitude,
                "depth": item.get("depth"),
            }
        )

    cache.set(CACHE_KEY, earthquakes, CACHE_TTL_SECONDS)
    return earthquakes


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
WEATHER_CACHE_TTL_SECONDS = 1800

WEATHER_CODE_LABELS = {
    0: "Açık", 1: "Az bulutlu", 2: "Parçalı bulutlu", 3: "Kapalı",
    45: "Sisli", 48: "Kırağı sisi",
    51: "Hafif çise", 53: "Çise", 55: "Yoğun çise",
    61: "Hafif yağmur", 63: "Yağmur", 65: "Kuvvetli yağmur",
    71: "Hafif kar", 73: "Kar", 75: "Kuvvetli kar",
    80: "Sağanak", 81: "Kuvvetli sağanak", 82: "Şiddetli sağanak",
    95: "Gök gürültülü fırtına",
}


def fetch_weather(city_name):
    """Open-Meteo'nun ücretsiz (API anahtarı gerektirmeyen) geocoding + hava
    durumu servislerinden bir il için güncel sıcaklık/durum bilgisi çeker.
    Sonuç 30 dakika önbelleklenir; ulaşılamazsa None döner (widget bu ili atlar)."""
    cache_key = f"weather_{city_name.strip().lower()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        geo_response = requests.get(
            GEOCODING_URL,
            params={"name": city_name, "count": 1, "language": "tr", "country": "TR"},
            timeout=5,
        )
        geo_response.raise_for_status()
        results = geo_response.json().get("results") or []
        if not results:
            logger.warning("Hava durumu: '%s' ili bulunamadı.", city_name)
            return None
        latitude, longitude = results[0]["latitude"], results[0]["longitude"]

        forecast_response = requests.get(
            FORECAST_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,weather_code",
                "timezone": "Europe/Istanbul",
            },
            timeout=5,
        )
        forecast_response.raise_for_status()
        current = forecast_response.json().get("current") or {}
    except (requests.RequestException, ValueError, KeyError, IndexError) as exc:
        logger.warning("Hava durumu alınamadı (%s): %s", city_name, exc)
        return None

    result = {
        "city": city_name,
        "temperature": current.get("temperature_2m"),
        "condition": WEATHER_CODE_LABELS.get(current.get("weather_code"), "—"),
    }
    cache.set(cache_key, result, WEATHER_CACHE_TTL_SECONDS)
    return result
