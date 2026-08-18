from django import template

from apps.content.models import WeatherLocation
from apps.content.services import fetch_weather
from apps.content.tr_map_data import TR_PROVINCES, VIEWBOX_H, VIEWBOX_W
from apps.teams.models import Team

register = template.Library()


@register.inclusion_tag("admin/includes/weather_widget.html")
def weather_widget():
    """Admin ana sayfasında, İçerik -> Hava Durumu İlleri'nde tanımlanan
    (aktif) illerin güncel hava durumunu gösterir."""
    items = []
    for location in WeatherLocation.objects.filter(is_active=True):
        data = fetch_weather(location.name)
        if data:
            items.append(data)
    return {"items": items}


# Team.city serbest metin bir alan; il isimleriyle eşleştirirken Türkçe
# büyük/küçük harf farklarına (İ/I) ve olası baş/son boşluklara karşı
# toleranslı olmak için normalize ediyoruz.
_TURKISH_LOWER_MAP = str.maketrans({"İ": "i", "I": "ı"})


def _normalize_city(name):
    return name.translate(_TURKISH_LOWER_MAP).lower().strip()


@register.inclusion_tag("admin/includes/team_cities_map.html")
def team_cities_map():
    """Admin ana sayfasında, ekiplerimizin bulunduğu şehirleri mavi
    gösteren Türkiye haritası. Team.city alanından okunur; her sayfa
    yüklemesinde yeniden hesaplandığından ekip eklenip/şehri
    değiştirildiğinde harita otomatik güncellenir."""
    province_by_normalized_name = {
        _normalize_city(name): name for name, _ in TR_PROVINCES
    }
    active_cities = set()
    for city in Team.objects.values_list("city", flat=True).distinct():
        matched = province_by_normalized_name.get(_normalize_city(city))
        if matched:
            active_cities.add(matched)

    provinces = [{"name": name, "d": d} for name, d in TR_PROVINCES]
    return {
        "provinces": provinces,
        "active_cities": active_cities,
        "active_count": len(active_cities),
        "viewbox": f"0 0 {VIEWBOX_W} {VIEWBOX_H}",
    }
