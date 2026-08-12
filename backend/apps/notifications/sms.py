import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

NAC_API_URL = "https://smslogin.nac.com.tr:9588/sms/create"


class SmsSendResult:
    def __init__(self, success, provider_message_id="", error=""):
        self.success = success
        self.provider_message_id = provider_message_id
        self.error = error


class NacSmsProvider:
    """NAC (nac.com.tr) MultiSms API entegrasyonu.

    Kimlik doğrulama: HTTP Basic Auth (kullanıcı adı:şifre base64).
    Uç nokta: POST /sms/create — NAC bu isteği tek bir "paket" (pkgID) olarak
    işliyor, numara bazlı değil paket bazlı sonuç dönüyor; bu yüzden tek bir
    istekteki tüm alıcılar aynı başarı/hata durumunu paylaşır.
    """

    def __init__(self):
        self.username = settings.NAC_SMS_USERNAME
        self.password = settings.NAC_SMS_PASSWORD
        self.sender = settings.NAC_SMS_SENDER_ID
        self.gateway = settings.NAC_SMS_GATEWAY_ID

    def send_bulk(self, phone_numbers, message, title):
        """phone_numbers: iterable[str]. title: NAC panelinde görünen 5-50
        karakterlik paket adı (alıcıya gitmez, sadece NAC'ın kendi raporlama
        tarafı için). Dönüş: {telefon_no: SmsSendResult}."""
        phone_numbers = list(phone_numbers)
        payload = {
            "type": 1,
            "sendingType": 1,
            "title": title,
            "content": message,
            "numbers": phone_numbers,
            "encoding": 1,  # Türkçe karakterler için
            "sender": self.sender,
            "validity": 60,
            "commercial": False,
            "skipAhsQuery": True,
            "recipientType": 0,
        }
        if self.gateway:
            payload["gateway"] = self.gateway

        try:
            response = requests.post(
                NAC_API_URL,
                json=payload,
                auth=(self.username, self.password),
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.error("NAC SMS gönderimi başarısız: %s", exc)
            return {number: SmsSendResult(False, error=str(exc)) for number in phone_numbers}

        err = data.get("err") or {}
        if err.get("code"):
            error_message = err.get("message") or err.get("code")
            logger.error("NAC SMS API hatası: %s", error_message)
            return {number: SmsSendResult(False, error=error_message) for number in phone_numbers}

        pkg_id = (data.get("data") or {}).get("pkgID")
        return {
            number: SmsSendResult(True, provider_message_id=str(pkg_id))
            for number in phone_numbers
        }
