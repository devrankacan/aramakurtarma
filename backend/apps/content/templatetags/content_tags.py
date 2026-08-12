from django import template

from apps.content.models import WeatherLocation
from apps.content.services import fetch_weather

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
