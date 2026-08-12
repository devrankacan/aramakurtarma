from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.forms_app.fields import EncryptedTextField


class User(AbstractUser):
    """Dernek personeli/gönüllüsü. Ekip üyeliği ve rolleri apps.teams üzerinden yönetilir."""

    phone_number = models.CharField("Telefon Numarası", max_length=20, blank=True)

    class Meta:
        verbose_name = "Kullanıcı"
        verbose_name_plural = "Kullanıcılar"

    def __str__(self):
        return self.get_full_name() or self.username


class BloodType(models.TextChoices):
    A_POS = "A+", "A Rh+"
    A_NEG = "A-", "A Rh-"
    B_POS = "B+", "B Rh+"
    B_NEG = "B-", "B Rh-"
    AB_POS = "AB+", "AB Rh+"
    AB_NEG = "AB-", "AB Rh-"
    O_POS = "0+", "0 Rh+"
    O_NEG = "0-", "0 Rh-"


class UserHealthProfile(models.Model):
    """Saha operasyonlarında dikkat edilmesi gereken sağlık bilgileri. Kan grubu ve acil
    durum iletişim bilgisi dışındaki alanlar KVKK özel nitelikli veri olduğu için
    alan-bazlı şifrelenir; sadece superuser görebilir, her görüntüleme kayıt altına alınır."""

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="health_profile", verbose_name="Kullanıcı"
    )
    blood_type = models.CharField(
        "Kan Grubu", max_length=3, choices=BloodType.choices, blank=True
    )
    chronic_conditions = EncryptedTextField(
        "Kronik Hastalıklar", blank=True, help_text="Varsa kronik rahatsızlıkları belirtin."
    )
    medications = EncryptedTextField(
        "Sürekli Kullanılan İlaçlar", blank=True
    )
    allergies = EncryptedTextField(
        "Alerjiler", blank=True, help_text="İlaç, gıda ya da diğer bilinen alerjiler."
    )
    fitness_notes = EncryptedTextField(
        "Fiziksel Uygunluk Notları",
        blank=True,
        help_text="Saha görevine engel olabilecek fiziksel durum notları.",
    )
    emergency_contact_name = models.CharField(
        "Acil Durum İrtibat Kişisi", max_length=150, blank=True
    )
    emergency_contact_phone = models.CharField(
        "Acil Durum İrtibat Telefonu", max_length=20, blank=True
    )
    last_medical_check_date = models.DateField(
        "Son Sağlık Kontrolü / Rapor Tarihi", null=True, blank=True
    )
    updated_at = models.DateTimeField("Güncellenme Tarihi", auto_now=True)

    class Meta:
        verbose_name = "Sağlık Profili"
        verbose_name_plural = "Sağlık Profilleri"

    def __str__(self):
        return f"{self.user} — Sağlık Profili"


class HealthProfileAccessLog(models.Model):
    """Bir kullanıcının sağlık profilinin kim tarafından ne zaman görüntülendiğinin
    kaydı — KVKK erişim izlenebilirliği için."""

    profile = models.ForeignKey(
        UserHealthProfile, on_delete=models.CASCADE, related_name="access_logs", verbose_name="Sağlık Profili"
    )
    accessed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
        verbose_name="Görüntüleyen",
    )
    accessed_at = models.DateTimeField("Görüntülenme Tarihi", auto_now_add=True)

    class Meta:
        verbose_name = "Sağlık Profili Erişim Kaydı"
        verbose_name_plural = "Sağlık Profili Erişim Kayıtları"
        ordering = ["-accessed_at"]

    def __str__(self):
        return f"{self.profile} — {self.accessed_by} — {self.accessed_at}"
