from django.contrib import admin

from .models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "start_at", "end_at", "location", "created_by")
    list_filter = ("teams",)
    date_hierarchy = "start_at"
    autocomplete_fields = ("teams",)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
