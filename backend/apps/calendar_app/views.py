from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from .templatetags.calendar_tags import build_calendar_context


@staff_member_required
def calendar_widget_partial(request):
    """Admin ana sayfasındaki Faaliyet Takvimi'nin JS ile (sayfa yenilenmeden)
    ay değiştirebilmesi için sadece takvim modülünü döner."""
    context = build_calendar_context(request)
    return render(request, "admin/includes/upcoming_events.html", context)
