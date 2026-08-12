from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from apps.teams.models import TeamMembership

from .models import User


class TeamMembershipInline(admin.TabularInline):
    model = TeamMembership
    extra = 1
    autocomplete_fields = ("team",)
    fields = ("team", "joined_at", "left_at")


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
    inlines = [TeamMembershipInline]
    list_display = ("username", "full_name", "email", "phone_number", "is_staff")

    @admin.display(description="Ad Soyad")
    def full_name(self, obj):
        return obj.get_full_name()
