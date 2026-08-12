from django.contrib import admin

from .models import AccreditationRequirement, CustodyAssignment, EquipmentCategory, InventoryItem


@admin.register(EquipmentCategory)
class EquipmentCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "unit")


@admin.register(AccreditationRequirement)
class AccreditationRequirementAdmin(admin.ModelAdmin):
    list_display = ("level", "category", "min_quantity")
    list_filter = ("level",)


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ("code", "category", "serial_number", "owner_team", "status", "expires_at")
    list_filter = ("status", "category", "owner_team")
    search_fields = ("code", "serial_number")


@admin.register(CustodyAssignment)
class CustodyAssignmentAdmin(admin.ModelAdmin):
    list_display = ("item", "assigned_to_user", "assigned_to_team", "assigned_at", "returned_at")
    list_filter = ("assigned_to_team",)
