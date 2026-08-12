from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Ek Bilgiler", {"fields": ("phone_number",)}),
    )
    list_display = ("username", "get_full_name", "email", "phone_number", "is_staff")
