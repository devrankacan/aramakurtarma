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
