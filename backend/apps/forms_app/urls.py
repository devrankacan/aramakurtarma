from django.urls import path

from .views import ExplicitConsentNoticeView, KvkkNoticeView, VolunteerApplicationCreateView

urlpatterns = [
    path("gonullu-ol/", VolunteerApplicationCreateView.as_view(), name="volunteer_apply"),
    path("kvkk-aydinlatma-metni/", KvkkNoticeView.as_view(), name="kvkk_notice"),
    path(
        "acik-riza-metni/",
        ExplicitConsentNoticeView.as_view(),
        name="explicit_consent_notice",
    ),
]
