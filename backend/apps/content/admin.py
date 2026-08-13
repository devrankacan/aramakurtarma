from django.contrib import admin
from django.utils.html import format_html

from .models import Announcement, KnowledgeBaseDocument, WeatherLocation


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("image_thumbnail", "title", "is_published", "published_at")
    list_filter = ("is_published",)
    list_editable = ("is_published",)
    search_fields = ("title", "body")
    date_hierarchy = "published_at"
    readonly_fields = ("image_preview",)
    fields = ("title", "body", "image", "image_preview", "is_published", "published_at")

    @admin.display(description="Önizleme")
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width:280px;max-height:180px;object-fit:cover;'
                'border-radius:8px;">',
                obj.image.url,
            )
        return "Görsel yüklenmedi."

    @admin.display(description="")
    def image_thumbnail(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width:40px;height:40px;object-fit:cover;'
                'border-radius:6px;">',
                obj.image.url,
            )
        return format_html(
            '<span style="display:inline-block;width:40px;height:40px;border-radius:6px;'
            'background:#dde3e8;"></span>'
        )


@admin.register(KnowledgeBaseDocument)
class KnowledgeBaseDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "is_published", "uploaded_at")
    list_filter = ("is_published",)
    search_fields = ("title",)


@admin.register(WeatherLocation)
class WeatherLocationAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "order")
    list_editable = ("is_active", "order")
