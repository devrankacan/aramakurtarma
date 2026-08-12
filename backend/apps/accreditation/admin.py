from django.contrib import admin

from .models import AccreditationLevel, AccreditationRecord, Certification, UserCertification


@admin.register(AccreditationLevel)
class AccreditationLevelAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "order")


@admin.register(Certification)
class CertificationAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "validity_period_days")


@admin.register(UserCertification)
class UserCertificationAdmin(admin.ModelAdmin):
    list_display = ("user", "certification", "issued_at", "expires_at")
    list_filter = ("certification",)


@admin.register(AccreditationRecord)
class AccreditationRecordAdmin(admin.ModelAdmin):
    list_display = ("team", "level", "status", "valid_from", "valid_until")
    list_filter = ("level", "status")
