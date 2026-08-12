from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from .views import HomeView

admin.site.site_header = "İyilik Derneği Arama Kurtarma"
admin.site.site_title = "AK Operasyon Paneli"
admin.site.index_title = "Yönetim Paneli"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("admin/", admin.site.urls),
    path("", include("apps.forms_app.urls")),
    path("", include("apps.content.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
