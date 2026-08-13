from django.contrib import admin

from .models import Announcement, KnowledgeBaseDocument, WeatherLocation


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "is_published", "published_at")
    list_filter = ("is_published",)
    list_editable = ("is_published",)
    search_fields = ("title", "body")
    date_hierarchy = "published_at"


@admin.register(KnowledgeBaseDocument)
class KnowledgeBaseDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "is_published", "uploaded_at")
    list_filter = ("is_published",)
    search_fields = ("title",)


@admin.register(WeatherLocation)
class WeatherLocationAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "order")
    list_editable = ("is_active", "order")
