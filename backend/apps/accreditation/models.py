from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.teams.models import Team


class AccreditationLevel(models.Model):
    """Akreditasyon seviyesi kataloğu (Hafif, Orta, ileride Ağır vb.).
    Kod olarak ayrı bir tablo tutulur ki yeni bir seviye eklemek kod değişikliği gerektirmesin."""

    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "Akreditasyon Seviyesi"
        verbose_name_plural = "Akreditasyon Seviyeleri"
        ordering = ["order"]

    def __str__(self):
        return self.name


class Certification(models.Model):
    """Kişisel sertifika/eğitim kataloğu (İleri İlk Yardım, İp Teknikleri vb.)."""

    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=150)
    validity_period_days = models.PositiveIntegerField(
        null=True, blank=True, help_text="Boş bırakılırsa süresiz kabul edilir."
    )

    class Meta:
        verbose_name = "Sertifika"
        verbose_name_plural = "Sertifikalar"

    def __str__(self):
        return self.name


class UserCertification(models.Model):
    """Bir kullanıcının sahip olduğu sertifika kaydı."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="certifications"
    )
    certification = models.ForeignKey(
        Certification, on_delete=models.PROTECT, related_name="holders"
    )
    issued_at = models.DateField()
    expires_at = models.DateField(null=True, blank=True)
    document_ref = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Kullanıcı Sertifikası"
        verbose_name_plural = "Kullanıcı Sertifikaları"
        unique_together = ("user", "certification", "issued_at")

    def __str__(self):
        return f"{self.user} — {self.certification}"


class AccreditationRecord(models.Model):
    """Bir ekibin belirli bir dönemdeki akreditasyon kaydı."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Aktif"
        PENDING = "pending", "Beklemede"
        EXPIRED = "expired", "Süresi Doldu"
        SUSPENDED = "suspended", "Askıya Alındı"

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="accreditation_records")
    level = models.ForeignKey(AccreditationLevel, on_delete=models.PROTECT, related_name="records")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    certifying_body = models.CharField(max_length=200, blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Akreditasyon Kaydı"
        verbose_name_plural = "Akreditasyon Kayıtları"

    def __str__(self):
        return f"{self.team} — {self.level} ({self.get_status_display()})"
