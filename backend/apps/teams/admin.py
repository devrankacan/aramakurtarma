from django import forms
from django.contrib import admin, messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import path

from .imports import build_template_workbook, parse_and_import
from .models import Role, Team, TeamMembership, UserTeamRole


class ExcelImportForm(forms.Form):
    file = forms.FileField(label="Excel Dosyası (.xlsx)")

    def clean_file(self):
        uploaded = self.cleaned_data["file"]
        if not uploaded.name.lower().endswith(".xlsx"):
            raise forms.ValidationError("Sadece .xlsx dosyaları kabul edilir.")
        return uploaded


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
    change_list_template = "admin/teams/teammembership/change_list.html"

    def get_urls(self):
        custom_urls = [
            path(
                "ice-aktar/",
                self.admin_site.admin_view(self.import_view),
                name="teams_teammembership_import",
            ),
            path(
                "ice-aktar/sablon/",
                self.admin_site.admin_view(self.template_view),
                name="teams_teammembership_import_template",
            ),
        ]
        return custom_urls + super().get_urls()

    def template_view(self, request):
        buffer = build_template_workbook()
        response = HttpResponse(
            buffer.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="ekip_uyeleri_sablonu.xlsx"'
        return response

    def import_view(self, request):
        if not self.has_add_permission(request):
            messages.error(request, "Bu işlem için yetkiniz yok.")
            return redirect("admin:teams_teammembership_changelist")

        if request.method == "POST":
            form = ExcelImportForm(request.POST, request.FILES)
            if form.is_valid():
                try:
                    result = parse_and_import(form.cleaned_data["file"])
                except ValueError as exc:
                    messages.error(request, str(exc))
                    return redirect("admin:teams_teammembership_import")
                except Exception:
                    messages.error(
                        request,
                        "Dosya okunamadı. Excel dosyasının bozuk olmadığından ve "
                        ".xlsx formatında olduğundan emin olun.",
                    )
                    return redirect("admin:teams_teammembership_import")

                context = {
                    **self.admin_site.each_context(request),
                    "title": "İçe Aktarma Sonuçları",
                    "opts": self.model._meta,
                    "result": result,
                }
                return render(
                    request, "admin/teams/teammembership/import_results.html", context
                )
        else:
            form = ExcelImportForm()

        context = {
            **self.admin_site.each_context(request),
            "title": "Ekip Üyelerini Excel'den İçe Aktar",
            "opts": self.model._meta,
            "form": form,
        }
        return render(request, "admin/teams/teammembership/import_excel.html", context)


@admin.register(UserTeamRole)
class UserTeamRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "team", "role", "assigned_at")
    list_filter = ("team", "role")
