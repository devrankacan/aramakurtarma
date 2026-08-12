from django.contrib import admin

from .models import SensitiveFieldAccessLog, VolunteerApplication


@admin.register(VolunteerApplication)
class VolunteerApplicationAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "city", "interested_area", "status", "consent_given_at")
    list_filter = ("status", "interested_area", "city")
    search_fields = ("first_name", "last_name", "email", "phone_number")
    readonly_fields = ("kvkk_consent", "health_data_consent", "consent_given_at")

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        if not request.user.is_superuser and "health_declaration" in fields:
            fields.remove("health_declaration")
        return fields

    def change_view(self, request, object_id, form_url="", extra_context=None):
        if request.user.is_superuser:
            SensitiveFieldAccessLog.objects.create(
                application_id=object_id, accessed_by=request.user
            )
        return super().change_view(request, object_id, form_url, extra_context)


@admin.register(SensitiveFieldAccessLog)
class SensitiveFieldAccessLogAdmin(admin.ModelAdmin):
    list_display = ("application", "accessed_by", "accessed_at")
    list_filter = ("accessed_by",)
    readonly_fields = ("application", "accessed_by", "accessed_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
