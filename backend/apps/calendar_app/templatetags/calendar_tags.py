from django.contrib.auth import get_user_model
from django import template
from django.utils import timezone

from apps.calendar_app.models import Event
from apps.teams.models import TeamMembership

register = template.Library()


def _next_occurrence(base_date, today):
    """base_date'in (yıl hariç) ay/gün bilgisine göre bugünden itibaren
    gelecekteki en yakın (bugün dahil) yıl dönümünü hesaplar. 29 Şubat gibi
    durumlar için normal yıllarda 28 Şubat'a düşürülür."""
    try:
        this_year = base_date.replace(year=today.year)
    except ValueError:
        this_year = base_date.replace(year=today.year, day=28)
    if this_year < today:
        try:
            return base_date.replace(year=today.year + 1)
        except ValueError:
            return base_date.replace(year=today.year + 1, day=28)
    return this_year


def _visible_team_ids(user):
    return user.team_memberships.filter(left_at__isnull=True).values_list("team_id", flat=True)


@register.inclusion_tag("admin/includes/upcoming_events.html", takes_context=True)
def upcoming_events(context, count=8):
    """Admin ana sayfasında 'Son eylemler' yerine gösterilen yaklaşan faaliyet listesi.
    Superuser tüm faaliyetleri görür; diğer kullanıcılar sadece kendi aktif üyesi
    oldukları ekiplere atanmış faaliyetleri görür."""
    request = context.get("request")
    user = getattr(request, "user", None)

    qs = Event.objects.filter(start_at__gte=timezone.now()).order_by("start_at")
    if user is not None and user.is_authenticated and not user.is_superuser:
        qs = qs.filter(teams__id__in=_visible_team_ids(user))

    return {"events": qs.distinct()[:count]}


@register.inclusion_tag("admin/includes/upcoming_birthdays.html", takes_context=True)
def upcoming_birthdays(context, days=30, count=10):
    """Bugünden itibaren `days` gün içindeki doğum günleri. Superuser herkesi
    görür, diğer kullanıcılar sadece kendi ekip arkadaşlarını görür."""
    request = context.get("request")
    user = getattr(request, "user", None)
    today = timezone.localdate()

    User = get_user_model()
    qs = User.objects.exclude(birth_date__isnull=True)
    if user is not None and user.is_authenticated and not user.is_superuser:
        qs = qs.filter(team_memberships__team_id__in=_visible_team_ids(user)).distinct()

    items = []
    for person in qs:
        next_date = _next_occurrence(person.birth_date, today)
        days_left = (next_date - today).days
        if days_left <= days:
            items.append(
                {
                    "user": person,
                    "date": next_date,
                    "age": next_date.year - person.birth_date.year,
                    "days_left": days_left,
                }
            )
    items.sort(key=lambda item: item["date"])
    return {"items": items[:count]}


@register.inclusion_tag("admin/includes/upcoming_anniversaries.html", takes_context=True)
def upcoming_anniversaries(context, days=30, count=10):
    """Bugünden itibaren `days` gün içindeki ekibe katılım yıl dönümleri
    (TeamMembership.joined_at). Superuser herkesi görür, diğer kullanıcılar
    sadece kendi ekip arkadaşlarını görür."""
    request = context.get("request")
    user = getattr(request, "user", None)
    today = timezone.localdate()

    qs = TeamMembership.objects.filter(left_at__isnull=True).select_related("user", "team")
    if user is not None and user.is_authenticated and not user.is_superuser:
        qs = qs.filter(team_id__in=_visible_team_ids(user))

    items = []
    for membership in qs:
        next_date = _next_occurrence(membership.joined_at, today)
        days_left = (next_date - today).days
        years = next_date.year - membership.joined_at.year
        if days_left <= days and years > 0:
            items.append({"membership": membership, "date": next_date, "years": years})
    items.sort(key=lambda item: item["date"])
    return {"items": items[:count]}
