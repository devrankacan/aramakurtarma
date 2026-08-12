from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.accreditation.models import AccreditationLevel
from apps.teams.models import Team


class EquipmentCategory(models.Model):
    """Envanter kalemi kategorisi (ör. İp, Sedye, İlk Yardım Çantası)."""

    name = models.CharField(max_length=150)
    unit = models.CharField(max_length=30, default="adet")

    class Meta:
        verbose_name = "Ekipman Kategorisi"
        verbose_name_plural = "Ekipman Kategorileri"

    def __str__(self):
        return self.name


class AccreditationRequirement(models.Model):
    """Bir akreditasyon seviyesinin zorunlu kıldığı ekipman/kategori ve asgari miktarı."""

    level = models.ForeignKey(
        AccreditationLevel, on_delete=models.CASCADE, related_name="requirements"
    )
    category = models.ForeignKey(
        EquipmentCategory, on_delete=models.PROTECT, related_name="requirements"
    )
    min_quantity = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "Akreditasyon Envanter Gereksinimi"
        verbose_name_plural = "Akreditasyon Envanter Gereksinimleri"
        unique_together = ("level", "category")

    def __str__(self):
        return f"{self.level} — {self.category}: {self.min_quantity}"


class InventoryItem(models.Model):
    """Fiziksel envanter kalemi (seri numaralı, takip edilen)."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Aktif"
        MAINTENANCE = "maintenance", "Bakımda"
        RETIRED = "retired", "Hizmet Dışı"
        LOST = "lost", "Kayıp"

    category = models.ForeignKey(
        EquipmentCategory, on_delete=models.PROTECT, related_name="items"
    )
    owner_team = models.ForeignKey(
        Team, on_delete=models.SET_NULL, null=True, blank=True, related_name="inventory_items"
    )
    serial_number = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    expires_at = models.DateField(
        null=True, blank=True, help_text="Son kullanma tarihi olan malzemeler için (ip, medikal vb.)."
    )

    class Meta:
        verbose_name = "Envanter Kalemi"
        verbose_name_plural = "Envanter Kalemleri"

    def __str__(self):
        return f"{self.category} — {self.serial_number or self.pk}"


class CustodyAssignment(models.Model):
    """Zimmet: bir envanter kaleminin kullanıcıya veya ekibe teslim/iade kaydı."""

    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name="custody_history")
    assigned_to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="custody_assignments",
    )
    assigned_to_team = models.ForeignKey(
        Team, on_delete=models.SET_NULL, null=True, blank=True, related_name="custody_assignments"
    )
    assigned_at = models.DateTimeField()
    returned_at = models.DateTimeField(null=True, blank=True)
    condition_notes = models.TextField(blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Zimmet Kaydı"
        verbose_name_plural = "Zimmet Kayıtları"

    def __str__(self):
        target = self.assigned_to_user or self.assigned_to_team
        return f"{self.item} — {target}"
