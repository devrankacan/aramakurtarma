from django.contrib import admin

from .models import KnowledgeBaseDocument, WeatherLocation


@admin.register(KnowledgeBaseDocument)
class KnowledgeBaseDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "is_published", "uploaded_at")
    list_filter = ("is_published",)
    search_fields = ("title",)


@admin.register(WeatherLocation)
class WeatherLocationAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "order")
    list_editable = ("is_active", "order")
