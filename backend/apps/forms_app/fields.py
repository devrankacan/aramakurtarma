from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


def _fernet():
    key = settings.FIELD_ENCRYPTION_KEY
    return Fernet(key.encode() if isinstance(key, str) else key)


class EncryptedTextField(models.TextField):
    """KVKK kapsamında özel nitelikli veri (ör. sağlık beyanı) için alan-bazlı
    şifreleme. Veritabanında düz metin değil, Fernet ile şifrelenmiş içerik tutulur."""

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if not value:
            return value
        return _fernet().encrypt(value.encode()).decode()

    def from_db_value(self, value, expression, connection):
        if not value:
            return value
        try:
            return _fernet().decrypt(value.encode()).decode()
        except InvalidToken:
            return value
