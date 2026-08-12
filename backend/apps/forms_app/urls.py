from django.urls import path

from .views import VolunteerApplicationCreateView

urlpatterns = [
    path("gonullu-ol/", VolunteerApplicationCreateView.as_view(), name="volunteer_apply"),
]
