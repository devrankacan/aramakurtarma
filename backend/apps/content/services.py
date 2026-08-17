import logging
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from xml.etree import ElementTree

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

# WMO hava kodu -> (etiket, ikon anahtarı). İkon anahtarları
# templates/admin/includes/weather_widget.html içindeki SVG'lerle eşleşir.
WEATHER_CODES = {
    0: ("Açık", "sun"),
    1: ("Az bulutlu", "cloud-sun"),
    2: ("Parçalı bulutlu", "cloud-sun"),
    3: ("Kapalı", "cloud"),
    45: ("Sisli", "fog"),
    48: ("Kırağı sisi", "fog"),
    51: ("Hafif çise", "rain"),
    53: ("Çise", "rain"),
    55: ("Yoğun çise", "rain"),
    61: ("Hafif yağmur", "rain"),
    63: ("Yağmur", "rain"),
    65: ("Kuvvetli yağmur", "rain"),
    71: ("Hafif kar", "snow"),
    73: ("Kar", "snow"),
    75: ("Kuvvetli kar", "snow"),
    80: ("Sağanak", "rain"),
    81: ("Kuvvetli sağanak", "rain"),
    82: ("Şiddetli sağanak", "rain"),
    95: ("Gök gürültülü fırtına", "storm"),
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

    condition, icon = WEATHER_CODES.get(current.get("weather_code"), ("—", "cloud"))
    result = {
        "city": city_name,
        "temperature": current.get("temperature_2m"),
        "condition": condition,
        "icon": icon,
    }
    cache.set(cache_key, result, WEATHER_CACHE_TTL_SECONDS)
    return result


# --- Afet Son Dakika Haberleri (anasayfa slider'ı) ---
# Kaynaklar: Anadolu Ajansı'nın herkese açık RSS akışı (anahtar kelimeyle
# filtrelenir) ve AFAD'ın yukarıda zaten doğrulanmış resmi deprem API'si
# (anlamlı büyüklükteki depremler haber kartına çevrilir). AFAD'ın genel
# haber/duyuru akışı için doğrulanmış herkese açık bir RSS/API bulunmadığından
# kurumsal siteyi scrape etmek yerine bu yol tercih edildi.
AA_RSS_URL = "https://www.aa.com.tr/tr/rss/default?cat=guncel"
DISASTER_KEYWORDS = [
    "deprem", "sel", "heyelan", "yangın", "hortum", "fırtına", "çığ",
    "tsunami", "afet", "göçük", "sağanak", "dolu", "kasırga",
]
DISASTER_NEWS_CACHE_KEY = "disaster_news_feed"
DISASTER_NEWS_CACHE_TTL_SECONDS = 900
MIN_NEWSWORTHY_MAGNITUDE = 4.0


def _matches_disaster_keywords(text):
    text_lower = (text or "").lower()
    return any(keyword in text_lower for keyword in DISASTER_KEYWORDS)


def _strip_html(text):
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _parse_afad_date(date_str):
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def fetch_aa_disaster_news(limit=8):
    """Anadolu Ajansı'nın herkese açık RSS akışından afetle ilgili (anahtar
    kelime eşleşen) haberleri çeker. Ulaşılamazsa/parse edilemezse boş liste
    döner."""
    try:
        response = requests.get(AA_RSS_URL, timeout=6)
        response.raise_for_status()
        root = ElementTree.fromstring(response.content)
    except (requests.RequestException, ElementTree.ParseError) as exc:
        logger.warning("AA RSS verisi alınamadı: %s", exc)
        return []

    items = []
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        description = _strip_html(unescape(item.findtext("description") or ""))
        if not _matches_disaster_keywords(f"{title} {description}"):
            continue

        pub_date_raw = item.findtext("pubDate")
        try:
            published_at = parsedate_to_datetime(pub_date_raw) if pub_date_raw else None
        except (TypeError, ValueError):
            published_at = None

        enclosure = item.find("enclosure")
        items.append(
            {
                "title": title,
                "summary": description[:220],
                "url": (item.findtext("link") or "").strip(),
                "image": enclosure.get("url") if enclosure is not None else None,
                "published_at": published_at or datetime.now(timezone.utc),
                "source": "Anadolu Ajansı",
            }
        )
        if len(items) >= limit:
            break
    return items


def _afad_earthquake_news_items(limit=4):
    """AFAD'ın doğrulanmış deprem API'sinden anlamlı büyüklükteki depremleri
    haber kartı formatına çevirir."""
    items = []
    for eq in fetch_recent_earthquakes(limit=15):
        magnitude = eq.get("magnitude")
        if magnitude is None or magnitude < MIN_NEWSWORTHY_MAGNITUDE:
            continue
        items.append(
            {
                "title": f"{magnitude} büyüklüğünde deprem — {eq['location']}",
                "summary": f"Derinlik: {eq['depth']} km" if eq.get("depth") else "",
                "url": "https://deprem.afad.gov.tr/last-earthquakes.html",
                "image": None,
                "published_at": _parse_afad_date(eq.get("date")) or datetime.now(timezone.utc),
                "source": "AFAD",
            }
        )
        if len(items) >= limit:
            break
    return items


def fetch_disaster_news(limit=8):
    """Anasayfadaki 'Afet Son Dakika' slider'ı için AA + AFAD kaynaklarını
    birleştirip tarihe göre sıralar. Sonuç 15 dakika önbelleklenir."""
    cached = cache.get(DISASTER_NEWS_CACHE_KEY)
    if cached is not None:
        return cached

    combined = fetch_aa_disaster_news(limit=limit) + _afad_earthquake_news_items(limit=4)
    combined.sort(key=lambda item: item["published_at"], reverse=True)
    result = combined[:limit]

    cache.set(DISASTER_NEWS_CACHE_KEY, result, DISASTER_NEWS_CACHE_TTL_SECONDS)
    return result
