from django.views.generic import TemplateView

from apps.content.services import fetch_recent_earthquakes


class HomeView(TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["earthquakes"] = fetch_recent_earthquakes(limit=10)
        return context
