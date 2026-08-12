import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class SmsSendResult:
    def __init__(self, success, provider_message_id="", error=""):
        self.success = success
        self.provider_message_id = provider_message_id
        self.error = error


class NacSmsProvider:
    """NAC (nac.com.tr) toplu SMS API entegrasyonu.

    ÖNEMLİ: NAC'ın gerçek API uç noktası, kimlik doğrulama yöntemi ve istek/yanıt
    formatı bu geliştirme ortamından doğrulanamadı (nac.com.tr bu ortamın ağ
    politikasınca engelli). Aşağıdaki istek şekli, Türkiye'deki toplu SMS
    sağlayıcılarının yaygın deseni baz alınarak yazıldı — NAC'ın kendi API
    dokümanıyla karşılaştırılıp doğrulanmadan production'da güvenilir kabul
    edilmemelidir.
    """

    def __init__(self):
        self.api_url = settings.NAC_SMS_API_URL
        self.api_key = settings.NAC_SMS_API_KEY
        self.username = settings.NAC_SMS_USERNAME
        self.password = settings.NAC_SMS_PASSWORD
        self.sender_id = settings.NAC_SMS_SENDER_ID

    def send_bulk(self, phone_numbers, message):
        """phone_numbers: iterable[str]. Tek istekte toplu gönderim dener.
        Dönüş: {telefon_no: SmsSendResult}."""
        phone_numbers = list(phone_numbers)
        payload = {
            "username": self.username,
            "password": self.password,
            "apiKey": self.api_key,
            "sender": self.sender_id,
            "message": message,
            "numbers": phone_numbers,
        }
        try:
            response = requests.post(self.api_url, json=payload, timeout=15)
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.error("NAC SMS gönderimi başarısız: %s", exc)
            return {number: SmsSendResult(False, error=str(exc)) for number in phone_numbers}

        # NAC'ın gerçek başarı yanıtı numara bazlı mı yoksa toplu mu döndüğü
        # doğrulanamadı; şimdilik istek başarılıysa tüm alıcılar için aynı
        # genel sonuç kaydediliyor. Gerçek API yanıtı elde edildiğinde
        # numara bazlı sonuç eşlemesi buraya yazılmalı.
        return {
            number: SmsSendResult(True, provider_message_id=str(data.get("id", "")))
            for number in phone_numbers
        }
