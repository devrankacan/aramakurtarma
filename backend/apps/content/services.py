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
# Bunlar afet OLAYLARININ ham verisi değil, afetlerle İLGİLİ gerçek haber
# makaleleri olmalı, dünya geneli olmalı ve Türkçe gösterilmeli. İki kaynak
# birleştirilir:
# 1) Anadolu Ajansı — herkese açık RSS ("güncel" + "dünya" kategorileri),
#    zaten Türkçe, anahtar kelimeyle filtrelenir, gerçek haber fotoğrafları
#    sunar. Ama kapsamı AA'nın o an neyi haber yaptığıyla sınırlı.
# 2) ReliefWeb (BM İnsani İşler Koordinasyon Ofisi - OCHA) — herkese açık,
#    zaten sadece afet/insani kriz haberlerinden oluşan, gerçekten dünya
#    genelini kapsayan RSS akışı. İçerik İngilizce olduğundan başlık/özet
#    Google Translate'in resmi olmayan (API anahtarı gerektirmeyen) genel
#    ağ geçidiyle Türkçeye çevrilir — bu resmi/garantili bir servis
#    değildir, en iyi çaba ile çalışır; çeviri başarısız olursa orijinal
#    İngilizce metin kullanılır. Görseli kullanılmaz (çoğunlukla PDF/rapor
#    eki simgesi çıkıyor, gerçek fotoğraf değil) — bunun yerine sabit
#    placeholder ikonu gösterilir.
# Ham deprem event verisi (AFAD/USGS gibi) burada kullanılmıyor; o veri
# sayfadaki ayrı "Son Depremler" tablosunda yer alıyor.
AA_RSS_URLS = [
    "https://www.aa.com.tr/tr/rss/default?cat=guncel",
    "https://www.aa.com.tr/tr/rss/default?cat=dunya",
]
RELIEFWEB_RSS_URL = "https://reliefweb.int/updates/rss.xml"
GOOGLE_TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"
DISASTER_KEYWORDS = [
    "deprem", "sel", "heyelan", "yangın", "hortum", "fırtına", "çığ",
    "tsunami", "afet", "göçük", "sağanak", "dolu", "kasırga",
]
DISASTER_NEWS_CACHE_KEY = "disaster_news_feed"
DISASTER_NEWS_CACHE_TTL_SECONDS = 900


# Python'un varsayılan (Türkçe olmayan) .lower()'ı "İ"yi "i̇", "I"yı "i"ye
# çevirir; "YANGIN" gibi büyük harfli başlıklarda "yangın" (ı) yerine
# "yangin" (i) çıkar ve anahtar kelime eşleşmesi kaçar. Türkçe kurallarına
# göre çeviriyoruz.
_TURKISH_LOWER_MAP = str.maketrans({"İ": "i", "I": "ı"})


def _matches_disaster_keywords(text):
    text_lower = (text or "").translate(_TURKISH_LOWER_MAP).lower()
    return any(keyword in text_lower for keyword in DISASTER_KEYWORDS)


def _strip_html(text):
    return re.sub(r"<[^>]+>", "", text or "").strip()


def fetch_aa_disaster_news(limit=8):
    """Anadolu Ajansı'nın herkese açık RSS akışlarından (güncel + dünya)
    afetle ilgili (anahtar kelime eşleşen) haberleri çeker. Ulaşılamazsa/
    parse edilemezse o kategoriyi atlar, hiçbiri çalışmazsa boş liste
    döner."""
    items = []
    seen_urls = set()
    for feed_url in AA_RSS_URLS:
        try:
            response = requests.get(feed_url, timeout=6)
            response.raise_for_status()
            root = ElementTree.fromstring(response.content)
        except (requests.RequestException, ElementTree.ParseError) as exc:
            logger.warning("AA RSS verisi alınamadı (%s): %s", feed_url, exc)
            continue

        for item in root.findall("./channel/item"):
            title = (item.findtext("title") or "").strip()
            description = _strip_html(unescape(item.findtext("description") or ""))
            if not _matches_disaster_keywords(f"{title} {description}"):
                continue

            url = (item.findtext("link") or "").strip()
            if url in seen_urls:
                continue
            seen_urls.add(url)

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
                    "url": url,
                    "image": enclosure.get("url") if enclosure is not None else None,
                    "published_at": published_at or datetime.now(timezone.utc),
                    "source": "Anadolu Ajansı",
                }
            )

    items.sort(key=lambda item: item["published_at"], reverse=True)
    return items[:limit]


def _translate_to_turkish(text):
    """Google Translate'in resmi olmayan, API anahtarı gerektirmeyen genel
    ağ geçidiyle İngilizce metni Türkçeye çevirir. Bu resmi/garantili bir
    servis değildir — ulaşılamazsa veya beklenmedik formatta dönerse
    orijinal metni değiştirmeden döner."""
    if not text:
        return text
    try:
        response = requests.get(
            GOOGLE_TRANSLATE_URL,
            params={"client": "gtx", "sl": "en", "tl": "tr", "dt": "t", "q": text},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=5,
        )
        response.raise_for_status()
        segments = response.json()[0]
        return "".join(segment[0] for segment in segments if segment[0])
    except (requests.RequestException, ValueError, IndexError, TypeError, KeyError) as exc:
        logger.warning("Çeviri başarısız, orijinal metin kullanılıyor: %s", exc)
        return text


def fetch_reliefweb_disaster_news(limit=5):
    """ReliefWeb'in (BM OCHA) herkese açık, dünya genelini kapsayan RSS
    akışından afet/insani kriz haberlerini çekip başlık ve özeti Türkçeye
    çevirir. Görseli kullanılmaz (çoğunlukla PDF/rapor eki simgesi çıkıyor);
    şablon tarafında sabit placeholder ikonu gösterilir. Ulaşılamazsa/parse
    edilemezse boş liste döner."""
    try:
        response = requests.get(RELIEFWEB_RSS_URL, timeout=6)
        response.raise_for_status()
        root = ElementTree.fromstring(response.content)
    except (requests.RequestException, ElementTree.ParseError) as exc:
        logger.warning("ReliefWeb RSS verisi alınamadı: %s", exc)
        return []

    items = []
    for item in root.findall("./channel/item")[:limit]:
        title_en = (item.findtext("title") or "").strip()
        description_en = _strip_html(unescape(item.findtext("description") or ""))[:220]

        pub_date_raw = item.findtext("pubDate")
        try:
            published_at = parsedate_to_datetime(pub_date_raw) if pub_date_raw else None
        except (TypeError, ValueError):
            published_at = None

        items.append(
            {
                "title": _translate_to_turkish(title_en),
                "summary": _translate_to_turkish(description_en),
                "url": (item.findtext("link") or "").strip(),
                "image": None,
                "published_at": published_at or datetime.now(timezone.utc),
                "source": "ReliefWeb (BM OCHA)",
            }
        )
    return items


def fetch_disaster_news(limit=8):
    """Anasayfadaki 'Afet Son Dakika' slider'ı için AA (Türkçe) + ReliefWeb
    (dünya geneli, Türkçeye çevrilmiş) kaynaklarını birleştirip tarihe göre
    sıralar. Sonuç 15 dakika önbelleklenir."""
    cached = cache.get(DISASTER_NEWS_CACHE_KEY)
    if cached is not None:
        return cached

    combined = fetch_aa_disaster_news(limit=limit) + fetch_reliefweb_disaster_news(limit=5)
    combined.sort(key=lambda item: item["published_at"], reverse=True)
    result = combined[:limit]

    cache.set(DISASTER_NEWS_CACHE_KEY, result, DISASTER_NEWS_CACHE_TTL_SECONDS)
    return result
