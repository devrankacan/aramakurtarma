from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from .fields import EncryptedTextField


class InterestArea(models.TextChoices):
    SEARCH = "arama", "Arama"
    RESCUE = "kurtarma", "Kurtarma"
    LOGISTICS = "lojistik", "Lojistik"
    FIRST_AID = "ilk_yardim", "İlk Yardım"
    K9 = "k9", "K9 (Arama Köpeği)"
    OTHER = "diger", "Diğer"


class VolunteerApplication(models.Model):
    """Herkese açık 'Gönüllü Ol' formundan gelen başvuru."""

    class Status(models.TextChoices):
        PENDING = "pending", "Değerlendirme Bekliyor"
        APPROVED = "approved", "Onaylandı"
        REJECTED = "rejected", "Reddedildi"

    first_name = models.CharField("Ad", max_length=100)
    last_name = models.CharField("Soyad", max_length=100)
    email = models.EmailField("E-posta")
    phone_number = models.CharField("Telefon", max_length=20)
    city = models.CharField("Şehir", max_length=100)
    birth_date = models.DateField("Doğum Tarihi")
    interested_area = models.CharField(
        "İlgilendiği Alan", max_length=20, choices=InterestArea.choices
    )
    motivation = models.TextField("Neden gönüllü olmak istiyorsunuz?")

    health_declaration = EncryptedTextField(
        "Sağlık Durumu / Fiziksel Uygunluk Beyanı",
        help_text="Saha çalışmasına engel olabilecek bir sağlık durumunuz varsa belirtin, yoksa 'yok' yazabilirsiniz.",
    )

    kvkk_consent = models.BooleanField(
        "KVKK Aydınlatma Metnini okudum, kişisel verilerimin işlenmesini kabul ediyorum."
    )
    health_data_consent = models.BooleanField(
        "Sağlık durumuma ilişkin özel nitelikli verimin bu başvuru kapsamında "
        "işlenmesine açıkça rıza gösteriyorum."
    )
    consent_given_at = models.DateTimeField("Başvuru Tarihi", auto_now_add=True)

    status = models.CharField(
        "Durum", max_length=20, choices=Status.choices, default=Status.PENDING
    )
    review_notes = models.TextField("Değerlendirme Notu", blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Gönüllü Başvurusu"
        verbose_name_plural = "Gönüllü Başvuruları"
        ordering = ["-consent_given_at"]

    def __str__(self):
        return f"{self.first_name} {self.last_name} — {self.get_status_display()}"


class SensitiveFieldAccessLog(models.Model):
    """Bir başvurunun özel nitelikli (sağlık) alanının kim tarafından ne zaman
    görüntülendiğinin kaydı — KVKK erişim izlenebilirliği için."""

    application = models.ForeignKey(
        VolunteerApplication,
        on_delete=models.CASCADE,
        related_name="access_logs",
        verbose_name="Başvuru",
    )
    accessed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Görüntüleyen",
    )
    accessed_at = models.DateTimeField("Görüntülenme Tarihi", auto_now_add=True)

    class Meta:
        verbose_name = "Hassas Veri Erişim Kaydı"
        verbose_name_plural = "Hassas Veri Erişim Kayıtları"
        ordering = ["-accessed_at"]

    def __str__(self):
        return f"{self.application} — {self.accessed_by} — {self.accessed_at}"
