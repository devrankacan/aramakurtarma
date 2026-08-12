from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.accreditation.models import AccreditationLevel
from apps.teams.models import Team


class EquipmentCategory(models.Model):
    """Envanter kalemi kategorisi (ör. İp, Sedye, İlk Yardım Çantası)."""

    name = models.CharField("Kategori Adı", max_length=150)
    unit = models.CharField("Birim", max_length=30, default="adet")

    class Meta:
        verbose_name = "Ekipman Kategorisi"
        verbose_name_plural = "Ekipman Kategorileri"

    def __str__(self):
        return self.name


class AccreditationRequirement(models.Model):
    """Bir akreditasyon seviyesinin zorunlu kıldığı ekipman/kategori ve asgari miktarı."""

    level = models.ForeignKey(
        AccreditationLevel,
        on_delete=models.CASCADE,
        related_name="requirements",
        verbose_name="Akreditasyon Seviyesi",
    )
    category = models.ForeignKey(
        EquipmentCategory,
        on_delete=models.PROTECT,
        related_name="requirements",
        verbose_name="Ekipman Kategorisi",
    )
    min_quantity = models.PositiveIntegerField("Asgari Miktar", default=1)

    class Meta:
        verbose_name = "Akreditasyon Envanter Gereksinimi"
        verbose_name_plural = "Akreditasyon Envanter Gereksinimleri"
        unique_together = ("level", "category")

    def __str__(self):
        return f"{self.level} — {self.category}: {self.min_quantity}"


class InventoryItem(models.Model):
    """Fiziksel envanter kalemi (seri numaralı, takip edilen)."""

    CODE_PREFIX = "ENV"

    class Status(models.TextChoices):
        ACTIVE = "active", "Aktif"
        MAINTENANCE = "maintenance", "Bakımda"
        RETIRED = "retired", "Hizmet Dışı"
        LOST = "lost", "Kayıp"

    code = models.CharField(
        "Envanter Kodu",
        max_length=20,
        unique=True,
        blank=True,
        help_text="Boş bırakılırsa sistem otomatik üretir (ör. ENV-00001). İstersen elle değiştirebilirsin.",
    )
    category = models.ForeignKey(
        EquipmentCategory, on_delete=models.PROTECT, related_name="items", verbose_name="Kategori"
    )
    owner_team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_items",
        verbose_name="Sahip Ekip",
    )
    serial_number = models.CharField("Seri Numarası", max_length=100, blank=True)
    status = models.CharField("Durum", max_length=20, choices=Status.choices, default=Status.ACTIVE)
    expires_at = models.DateField(
        "Son Kullanma Tarihi",
        null=True,
        blank=True,
        help_text="Son kullanma tarihi olan malzemeler için (ip, medikal vb.).",
    )

    class Meta:
        verbose_name = "Envanter Kalemi"
        verbose_name_plural = "Envanter Kalemleri"

    def __str__(self):
        return f"{self.code} — {self.category}"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self._generate_next_code()
        super().save(*args, **kwargs)

    @classmethod
    def _generate_next_code(cls):
        prefix = f"{cls.CODE_PREFIX}-"
        last_item = (
            cls.objects.filter(code__startswith=prefix).order_by("-code").first()
        )
        last_number = 0
        if last_item:
            try:
                last_number = int(last_item.code[len(prefix):])
            except ValueError:
                last_number = 0
        return f"{prefix}{last_number + 1:05d}"


class CustodyAssignment(models.Model):
    """Zimmet: bir envanter kaleminin kullanıcıya veya ekibe teslim/iade kaydı."""

    item = models.ForeignKey(
        InventoryItem,
        on_delete=models.CASCADE,
        related_name="custody_history",
        verbose_name="Envanter Kalemi",
    )
    assigned_to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="custody_assignments",
        verbose_name="Zimmetli Kullanıcı",
    )
    assigned_to_team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="custody_assignments",
        verbose_name="Zimmetli Ekip",
    )
    assigned_at = models.DateTimeField("Teslim Tarihi")
    returned_at = models.DateTimeField("İade Tarihi", null=True, blank=True)
    condition_notes = models.TextField("Durum Notları", blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Zimmet Kaydı"
        verbose_name_plural = "Zimmet Kayıtları"

    def __str__(self):
        target = self.assigned_to_user or self.assigned_to_team
        return f"{self.item} — {target}"
