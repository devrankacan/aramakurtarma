from django.contrib import admin

from .models import Role, Team, TeamMembership, UserTeamRole


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "created_at")
    list_filter = ("city",)
    search_fields = ("name", "city")


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "code")


@admin.register(TeamMembership)
class TeamMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "team", "joined_at", "left_at", "is_active")
    list_filter = ("team",)


@admin.register(UserTeamRole)
class UserTeamRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "team", "role", "assigned_at")
    list_filter = ("team", "role")
