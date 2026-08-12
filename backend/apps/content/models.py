from django.core.validators import FileExtensionValidator
from django.db import models


class KnowledgeBaseDocument(models.Model):
    """Bilgi Bankası'nda listelenen, admin panelinden yüklenen PDF doküman."""

    title = models.CharField("Başlık", max_length=200)
    description = models.TextField("Açıklama", blank=True)
    file = models.FileField(
        "PDF Dosyası",
        upload_to="knowledge_base/%Y/%m/",
        validators=[FileExtensionValidator(["pdf"])],
    )
    is_published = models.BooleanField("Yayınla", default=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Bilgi Bankası Dokümanı"
        verbose_name_plural = "Bilgi Bankası Dokümanları"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.title
