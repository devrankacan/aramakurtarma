import calendar as cal_module
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django import template
from django.utils import timezone

from apps.calendar_app.models import Event
from apps.teams.models import TeamMembership

register = template.Library()

TURKISH_MONTHS = [
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
]
# Pazartesi başlangıçlı; son iki gün (Ct, Pz) hafta sonu.
TURKISH_WEEKDAYS = [
    {"label": "Pt", "is_weekend": False},
    {"label": "Sa", "is_weekend": False},
    {"label": "Ça", "is_weekend": False},
    {"label": "Pe", "is_weekend": False},
    {"label": "Cu", "is_weekend": False},
    {"label": "Ct", "is_weekend": True},
    {"label": "Pz", "is_weekend": True},
]


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


def _first_of_next_month(d):
    return (d.replace(day=28) + timedelta(days=4)).replace(day=1)


def _first_of_prev_month(d):
    return (d.replace(day=1) - timedelta(days=1)).replace(day=1)


def build_calendar_context(request):
    """upcoming_events template tag'i ile calendar_widget_partial view'ının
    ortak kullandığı hesaplama. Görüntülenen ay `?month=YYYY-MM` GET
    parametresiyle değiştirilebilir; parametre yoksa/hatalıysa bugünün ayı
    gösterilir. Superuser tüm faaliyetleri görür; diğer kullanıcılar sadece
    kendi aktif üyesi oldukları ekiplere atanmış faaliyetleri görür."""
    user = getattr(request, "user", None)
    today = timezone.localdate()

    month_param = request.GET.get("month") if request else None
    month_start = today.replace(day=1)
    if month_param:
        try:
            year_str, month_str = month_param.split("-")
            month_start = date(int(year_str), int(month_str), 1)
        except (ValueError, TypeError):
            month_start = today.replace(day=1)

    qs = Event.objects.all()
    if user is not None and user.is_authenticated and not user.is_superuser:
        qs = qs.filter(teams__id__in=_visible_team_ids(user))

    next_month_start = _first_of_next_month(month_start)
    month_events = qs.filter(
        start_at__date__gte=month_start, start_at__date__lt=next_month_start
    ).order_by("start_at").distinct()

    events_by_day = {}
    for event in month_events:
        events_by_day.setdefault(event.start_at.date(), []).append(event)

    cal_module.setfirstweekday(cal_module.MONDAY)
    weeks = []
    for week in cal_module.monthcalendar(month_start.year, month_start.month):
        week_days = []
        for weekday_index, day_num in enumerate(week):
            if day_num == 0:
                week_days.append(None)
            else:
                day_date = month_start.replace(day=day_num)
                week_days.append(
                    {
                        "day": day_num,
                        "is_today": day_date == today,
                        "is_weekend": weekday_index >= 5,
                        "events": events_by_day.get(day_date, []),
                    }
                )
        weeks.append(week_days)

    return {
        "weeks": weeks,
        "weekdays": TURKISH_WEEKDAYS,
        "month_label": f"{TURKISH_MONTHS[month_start.month - 1]} {month_start.year}",
        "prev_month_param": _first_of_prev_month(month_start).strftime("%Y-%m"),
        "next_month_param": next_month_start.strftime("%Y-%m"),
    }


@register.inclusion_tag("admin/includes/upcoming_events.html", takes_context=True)
def upcoming_events(context):
    """Admin ana sayfasında 'Son eylemler' yerine gösterilen aylık mini takvim.
    Bir günün faaliyet(ler)i o günün hücresinde küçük bir kart olarak görünür."""
    return build_calendar_context(context.get("request"))


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
