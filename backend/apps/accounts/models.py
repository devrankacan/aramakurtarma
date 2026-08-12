from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Dernek personeli/gönüllüsü. Ekip üyeliği ve rolleri apps.teams üzerinden yönetilir."""

    phone_number = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return self.get_full_name() or self.username
