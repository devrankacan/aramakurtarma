from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from apps.teams.models import TeamMembership

from .models import HealthProfileAccessLog, User, UserHealthProfile


class TeamMembershipInline(admin.TabularInline):
    model = TeamMembership
    extra = 1
    autocomplete_fields = ("team",)
    fields = ("team", "joined_at", "left_at")


SENSITIVE_HEALTH_FIELDS = {"chronic_conditions", "medications", "allergies", "fitness_notes"}


class UserHealthProfileInline(admin.StackedInline):
    model = UserHealthProfile
    can_delete = False
    max_num = 1
    verbose_name = "Sağlık Profili"
    verbose_name_plural = "Sağlık Profili"

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        if not request.user.is_superuser:
            fields = [f for f in fields if f not in SENSITIVE_HEALTH_FIELDS]
        return fields


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    # Django'nun varsayılan "Gruplar" / "Kullanıcı izinleri" alanları (her model
    # için tek tek add/change/delete/view izni listesi) burada kullanılmıyor —
    # yetkilendirme apps.teams.UserTeamRole ile yönetiliyor. Onun yerine
    # kullanıcının bağlı olduğu ekip(ler) doğrudan bu sayfada (inline) düzenlenir.
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Kişisel Bilgiler", {"fields": ("first_name", "last_name", "email", "phone_number")}),
        ("Yetkiler", {"fields": ("is_active", "is_staff", "is_superuser")}),
        ("Önemli Tarihler", {"fields": ("last_login", "date_joined")}),
    )
    inlines = [TeamMembershipInline, UserHealthProfileInline]
    list_display = ("username", "full_name", "email", "phone_number", "is_staff")

    @admin.display(description="Ad Soyad")
    def full_name(self, obj):
        return obj.get_full_name()

    def change_view(self, request, object_id, form_url="", extra_context=None):
        if request.user.is_superuser:
            profile = UserHealthProfile.objects.filter(user_id=object_id).first()
            if profile:
                HealthProfileAccessLog.objects.create(profile=profile, accessed_by=request.user)
        return super().change_view(request, object_id, form_url, extra_context)


@admin.register(HealthProfileAccessLog)
class HealthProfileAccessLogAdmin(admin.ModelAdmin):
    list_display = ("profile", "accessed_by", "accessed_at")
    list_filter = ("accessed_by",)
    readonly_fields = ("profile", "accessed_by", "accessed_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
