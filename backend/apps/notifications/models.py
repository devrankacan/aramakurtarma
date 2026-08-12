from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models

from apps.teams.models import Team


class SmsCampaign(models.Model):
    """Ekiplere (ya da tüm kullanıcılara) gönderilen, ya da taslak halindeki toplu SMS gönderimi."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Taslak"
        SENT = "sent", "Gönderildi"
        FAILED = "failed", "Başarısız"

    teams = models.ManyToManyField(
        Team, blank=True, related_name="sms_campaigns", verbose_name="Hedef Ekipler"
    )
    include_all_users = models.BooleanField(
        "Tüm Kullanıcılar",
        default=False,
        help_text="İşaretlenirse ekip seçimi yok sayılır, telefon numarası olan tüm "
        "kullanıcılara gönderilir.",
    )
    message = models.TextField(
        "Mesaj Metni",
        help_text="459 karakteri aşan mesajlar birden fazla SMS olarak ücretlendirilebilir.",
    )
    status = models.CharField(
        "Durum", max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Oluşturan",
    )
    created_at = models.DateTimeField("Oluşturulma Tarihi", auto_now_add=True)
    sent_at = models.DateTimeField("Gönderim Tarihi", null=True, blank=True)
    recipient_count = models.PositiveIntegerField("Alıcı Sayısı", default=0)
    provider_response = models.JSONField("Sağlayıcı Yanıtı", null=True, blank=True)

    class Meta:
        verbose_name = "Toplu SMS Gönderimi"
        verbose_name_plural = "Toplu SMS Gönderimleri"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.target_display()} — {self.get_status_display()}"

    def target_display(self):
        if self.include_all_users:
            return "Tüm Kullanıcılar"
        if self.pk:
            names = list(self.teams.values_list("name", flat=True))
            if names:
                return ", ".join(names)
        return "Hedef seçilmedi"

    target_display.short_description = "Hedef"

    def resolve_recipients(self):
        """Seçili ekiplerdeki (ya da tüm) telefon numarası girilmiş kullanıcıları döner."""
        User = get_user_model()
        if self.include_all_users:
            return User.objects.exclude(phone_number="").distinct()

        team_ids = list(self.teams.values_list("id", flat=True))
        return (
            User.objects.filter(
                team_memberships__team_id__in=team_ids,
                team_memberships__left_at__isnull=True,
            )
            .exclude(phone_number="")
            .distinct()
        )


class SmsRecipientLog(models.Model):
    """Bir kampanyanın tek bir alıcıya gönderim sonucu (raporlama için)."""

    campaign = models.ForeignKey(
        SmsCampaign, on_delete=models.CASCADE, related_name="recipient_logs", verbose_name="Gönderim"
    )
    phone_number = models.CharField("Telefon Numarası", max_length=20)
    is_success = models.BooleanField("Başarılı mı", default=False)
    provider_message_id = models.CharField("Sağlayıcı Mesaj ID", max_length=100, blank=True)
    error_detail = models.TextField("Hata Detayı", blank=True)

    class Meta:
        verbose_name = "SMS Alıcı Kaydı"
        verbose_name_plural = "SMS Alıcı Kayıtları"

    def __str__(self):
        return f"{self.phone_number} — {'OK' if self.is_success else 'Hata'}"
