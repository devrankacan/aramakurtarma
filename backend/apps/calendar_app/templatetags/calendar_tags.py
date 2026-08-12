from django import template
from django.utils import timezone

from apps.calendar_app.models import Event

register = template.Library()


@register.inclusion_tag("admin/includes/upcoming_events.html", takes_context=True)
def upcoming_events(context, count=8):
    """Admin ana sayfasında 'Son eylemler' yerine gösterilen yaklaşan faaliyet listesi.
    Superuser tüm faaliyetleri görür; diğer kullanıcılar sadece kendi aktif üyesi
    oldukları ekiplere atanmış faaliyetleri görür."""
    request = context.get("request")
    user = getattr(request, "user", None)

    qs = Event.objects.filter(start_at__gte=timezone.now()).order_by("start_at")
    if user is not None and user.is_authenticated and not user.is_superuser:
        team_ids = user.team_memberships.filter(left_at__isnull=True).values_list(
            "team_id", flat=True
        )
        qs = qs.filter(teams__id__in=team_ids)

    return {"events": qs.distinct()[:count]}
