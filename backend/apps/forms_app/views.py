from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView

from .forms import VolunteerApplicationForm


class VolunteerApplicationCreateView(CreateView):
    form_class = VolunteerApplicationForm
    template_name = "forms_app/volunteer_apply.html"
    success_url = reverse_lazy("volunteer_apply")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            "Başvurunuz alındı. Değerlendirme sonrası sizinle iletişime geçilecek.",
        )
        return response


class KvkkNoticeView(TemplateView):
    template_name = "forms_app/kvkk_notice.html"


class ExplicitConsentNoticeView(TemplateView):
    template_name = "forms_app/explicit_consent_notice.html"
