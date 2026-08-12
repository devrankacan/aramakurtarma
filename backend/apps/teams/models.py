from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords


class Team(models.Model):
    """Ekip (ör. Arama Kurtarma Ekibi 1). Ekipler şehir bazlı ayrılır."""

    name = models.CharField("Ekip Adı", max_length=200)
    city = models.CharField("Şehir", max_length=100)
    created_at = models.DateTimeField("Oluşturulma Tarihi", auto_now_add=True)

    class Meta:
        verbose_name = "Ekip"
        verbose_name_plural = "Ekipler"
        unique_together = ("city", "name")

    def __str__(self):
        return f"{self.name} ({self.city})"


class Role(models.Model):
    """Operasyonel rol kataloğu (Ekip Amiri, Lojistik, İlk Yardımcı, Arama, Kurtarma, K9 vb.)."""

    code = models.SlugField("Kod", max_length=50, unique=True)
    name = models.CharField("Rol Adı", max_length=100)
    description = models.TextField("Açıklama", blank=True)

    class Meta:
        verbose_name = "Rol"
        verbose_name_plural = "Roller"

    def __str__(self):
        return self.name


class TeamMembership(models.Model):
    """Bir kullanıcının bir ekibe üyeliği (katılma/ayrılma tarihli)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="team_memberships",
        verbose_name="Kullanıcı",
    )
    team = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name="memberships", verbose_name="Ekip"
    )
    joined_at = models.DateField("Katılma Tarihi")
    left_at = models.DateField("Ayrılma Tarihi", null=True, blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Ekip Üyeliği"
        verbose_name_plural = "Ekip Üyelikleri"

    def __str__(self):
        return f"{self.user} — {self.team}"

    @property
    def is_active(self):
        return self.left_at is None

    is_active.fget.short_description = "Aktif mi"


class UserTeamRole(models.Model):
    """Kullanıcının belirli bir ekipteki rolü. Rol, kullanıcıya değil bu ilişkiye bağlıdır:
    aynı kişi farklı ekiplerde farklı rollere sahip olabilir."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="team_roles",
        verbose_name="Kullanıcı",
    )
    team = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name="member_roles", verbose_name="Ekip"
    )
    role = models.ForeignKey(
        Role, on_delete=models.PROTECT, related_name="assignments", verbose_name="Rol"
    )
    assigned_at = models.DateTimeField("Atanma Tarihi", auto_now_add=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Ekip İçi Rol Ataması"
        verbose_name_plural = "Ekip İçi Rol Atamaları"
        unique_together = ("user", "team", "role")

    def __str__(self):
        return f"{self.user} — {self.team} — {self.role}"
