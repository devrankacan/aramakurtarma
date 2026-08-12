from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models

from apps.teams.models import Role, Team


class NotificationSegment(models.Model):
    """Toplu SMS/bildirim gönderilecek hedef kitleyi tanımlayan dinamik filtre."""

    name = models.CharField("Grup Adı", max_length=150)
    teams = models.ManyToManyField(
        Team, blank=True, related_name="notification_segments", verbose_name="Ekipler"
    )
    roles = models.ManyToManyField(
        Role, blank=True, related_name="notification_segments", verbose_name="Roller"
    )
    include_all_users = models.BooleanField(
        "Tüm Kullanıcılar",
        default=False,
        help_text="İşaretlenirse ekip/rol filtresi yok sayılır, telefon numarası olan tüm "
        "kullanıcılar hedeflenir.",
    )
    created_at = models.DateTimeField("Oluşturulma Tarihi", auto_now_add=True)

    class Meta:
        verbose_name = "Bildirim Grubu"
        verbose_name_plural = "Bildirim Grupları"

    def __str__(self):
        return self.name

    def resolve_recipients(self):
        """Filtreye uyan, telefon numarası girilmiş kullanıcıları döner."""
        User = get_user_model()
        if self.include_all_users:
            return User.objects.exclude(phone_number="").distinct()

        team_ids = list(self.teams.values_list("id", flat=True))
        role_ids = list(self.roles.values_list("id", flat=True))
        return (
            User.objects.filter(
                models.Q(
                    team_memberships__team_id__in=team_ids,
                    team_memberships__left_at__isnull=True,
                )
                | models.Q(team_roles__role_id__in=role_ids)
            )
            .exclude(phone_number="")
            .distinct()
        )


class SmsCampaign(models.Model):
    """Bir hedef gruba gönderilen (ya da taslak halindeki) toplu SMS gönderimi."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Taslak"
        SENT = "sent", "Gönderildi"
        FAILED = "failed", "Başarısız"

    segment = models.ForeignKey(
        NotificationSegment,
        on_delete=models.PROTECT,
        related_name="campaigns",
        verbose_name="Hedef Grup",
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
        return f"{self.segment} — {self.get_status_display()}"


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
