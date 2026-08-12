from django.conf import settings
from django.db import models

from apps.teams.models import Team


class Event(models.Model):
    """Admin tarafından eklenen faaliyet (tatbikat, toplantı, operasyon vb.).
    Sadece seçili ekip(ler)in üyelerine görünür."""

    title = models.CharField("Başlık", max_length=200)
    description = models.TextField("Açıklama", blank=True)
    start_at = models.DateTimeField("Başlangıç")
    end_at = models.DateTimeField("Bitiş", null=True, blank=True)
    location = models.CharField("Konum", max_length=200, blank=True)
    teams = models.ManyToManyField(Team, related_name="events", verbose_name="İlgili Ekipler")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Oluşturan",
    )
    created_at = models.DateTimeField("Oluşturulma Tarihi", auto_now_add=True)

    class Meta:
        verbose_name = "Faaliyet"
        verbose_name_plural = "Faaliyetler"
        ordering = ["start_at"]

    def __str__(self):
        return f"{self.title} — {self.start_at:%d.%m.%Y %H:%M}"
