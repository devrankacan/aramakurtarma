from django.contrib import admin

from .models import KnowledgeBaseDocument


@admin.register(KnowledgeBaseDocument)
class KnowledgeBaseDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "is_published", "uploaded_at")
    list_filter = ("is_published",)
    search_fields = ("title",)
