from django.contrib import admin, messages
from django.utils import timezone

from .models import SmsCampaign, SmsRecipientLog
from .sms import NacSmsProvider


class SmsRecipientLogInline(admin.TabularInline):
    model = SmsRecipientLog
    extra = 0
    readonly_fields = ("phone_number", "is_success", "provider_message_id", "error_detail")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(SmsCampaign)
class SmsCampaignAdmin(admin.ModelAdmin):
    list_display = ("target_display", "status", "recipient_count", "created_by", "created_at", "sent_at")
    list_filter = ("status", "teams")
    autocomplete_fields = ("teams",)
    readonly_fields = ("status", "created_by", "sent_at", "recipient_count", "provider_response")
    inlines = [SmsRecipientLogInline]
    actions = ["send_campaign"]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description="Seçili taslakları gönder")
    def send_campaign(self, request, queryset):
        provider = NacSmsProvider()
        for campaign in queryset.filter(status=SmsCampaign.Status.DRAFT):
            recipients = list(
                campaign.resolve_recipients().values_list("phone_number", flat=True)
            )
            if not recipients:
                self.message_user(
                    request, f"{campaign}: alıcı bulunamadı, atlandı.", level=messages.WARNING
                )
                continue

            results = provider.send_bulk(
                recipients, campaign.message, title=f"AramaKurtarma-{campaign.pk}"
            )
            SmsRecipientLog.objects.bulk_create(
                [
                    SmsRecipientLog(
                        campaign=campaign,
                        phone_number=number,
                        is_success=result.success,
                        provider_message_id=result.provider_message_id,
                        error_detail=result.error,
                    )
                    for number, result in results.items()
                ]
            )
            success_count = sum(1 for r in results.values() if r.success)
            campaign.status = (
                SmsCampaign.Status.SENT if success_count else SmsCampaign.Status.FAILED
            )
            campaign.recipient_count = len(recipients)
            campaign.sent_at = timezone.now()
            campaign.save(update_fields=["status", "recipient_count", "sent_at"])

            level = messages.SUCCESS if success_count == len(recipients) else messages.WARNING
            self.message_user(
                request,
                f"{campaign}: {success_count}/{len(recipients)} numaraya gönderildi.",
                level=level,
            )


@admin.register(SmsRecipientLog)
class SmsRecipientLogAdmin(admin.ModelAdmin):
    list_display = ("campaign", "phone_number", "is_success")
    list_filter = ("is_success", "campaign")
    search_fields = ("phone_number",)

    def has_add_permission(self, request):
        return False
