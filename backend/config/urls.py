from django.contrib import admin
from django.urls import path

admin.site.site_header = "İyilik Derneği Arama Kurtarma"
admin.site.site_title = "AK Operasyon Paneli"
admin.site.index_title = "Yönetim Paneli"

urlpatterns = [
    path("admin/", admin.site.urls),
]
