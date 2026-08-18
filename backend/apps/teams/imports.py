"""Excel'den (.xlsx) toplu ekip üyesi içe aktarma.

Kullanım: admin panelinde Ekip Üyelikleri -> İçe Aktar. Beklenen sütun
başlıkları (ilk satır, TEMPLATE_HEADERS ile birebir aynı sırada/isimde
olması zorunlu değil, isimle eşleştirilir):

    Ad*, Soyad*, Ekip Adı*, Ekip Şehri, E-posta, Telefon,
    Doğum Tarihi, Katılma Tarihi, Kullanıcı Adı

(*) zorunlu alanlar. "Ekip Şehri" sadece aynı isimde birden fazla ekip
varsa zorunlu hale gelir. "Kullanıcı Adı" boş bırakılırsa Ad.Soyad'dan
otomatik üretilir — mevcut bir kişiyi başka bir ekibe eklemek için bu
alana onun mevcut kullanıcı adını yazmak gerekir, aksi halde ikinci bir
hesap oluşturulur.
"""

import io
import re
import secrets
import string
from datetime import date, datetime

import openpyxl
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.teams.models import Team, TeamMembership

User = get_user_model()

TEMPLATE_HEADERS = [
    "Ad",
    "Soyad",
    "Ekip Adı",
    "Ekip Şehri",
    "E-posta",
    "Telefon",
    "Doğum Tarihi",
    "Katılma Tarihi",
    "Kullanıcı Adı",
]
TEMPLATE_EXAMPLE_ROW = [
    "Ayşe",
    "Yılmaz",
    "Arama Kurtarma Ekibi 1",
    "İstanbul",
    "ayse.yilmaz@example.com",
    "0555 000 00 00",
    "15.03.1995",
    "01.06.2026",
    "",
]

REQUIRED_HEADERS = {"Ad", "Soyad", "Ekip Adı"}

_TR_ASCII_MAP = str.maketrans({
    "ç": "c", "Ç": "c", "ğ": "g", "Ğ": "g", "ı": "i", "I": "i", "İ": "i",
    "ö": "o", "Ö": "o", "ş": "s", "Ş": "s", "ü": "u", "Ü": "u",
})


def build_template_workbook():
    """İndirilebilir boş şablon (başlık satırı + 1 örnek satır)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Ekip Üyeleri"
    ws.append(TEMPLATE_HEADERS)
    ws.append(TEMPLATE_EXAMPLE_ROW)
    for col_idx, header in enumerate(TEMPLATE_HEADERS, start=1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = max(18, len(header) + 4)
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def _cell_text(value):
    if value is None:
        return ""
    return str(value).strip()


def _parse_date(value):
    """Excel tarih hücresi (datetime) veya metin (GG.AA.YYYY / GG/AA/YYYY /
    YYYY-AA-GG) kabul eder. Ayrıştırılamazsa None döner."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _slugify_username(ad, soyad):
    base = f"{ad}.{soyad}".translate(_TR_ASCII_MAP).lower()
    base = re.sub(r"[^a-z0-9.]+", "", base).strip(".") or "kullanici"
    username = base
    suffix = 1
    while User.objects.filter(username=username).exists():
        suffix += 1
        username = f"{base}{suffix}"
    return username


def _generate_password():
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(12))


def _resolve_team(team_name, team_city, row_errors):
    if not team_name:
        row_errors.append("Ekip Adı boş olamaz.")
        return None
    qs = Team.objects.filter(name__iexact=team_name)
    if team_city:
        qs = qs.filter(city__iexact=team_city)
    matches = list(qs[:2])
    if not matches:
        row_errors.append(f"'{team_name}' adında (ve varsa '{team_city}' şehrinde) ekip bulunamadı.")
        return None
    if len(matches) > 1:
        row_errors.append(
            f"'{team_name}' adında birden fazla ekip var, hangisi olduğunu belirlemek için "
            f"'Ekip Şehri' sütununu doldurun."
        )
        return None
    return matches[0]


def parse_and_import(uploaded_file):
    """Excel dosyasını okuyup satır satır işler. Her satır kendi
    transaction'ında; bir satırdaki hata diğerlerini etkilemez.
    Dönüş: {"rows": [...], "created_count": int, "error_count": int}."""
    wb = openpyxl.load_workbook(uploaded_file, data_only=True)
    ws = wb.active

    header_row = [
        _cell_text(cell.value) for cell in next(ws.iter_rows(min_row=1, max_row=1))
    ]
    header_index = {header: idx for idx, header in enumerate(header_row) if header}

    missing = REQUIRED_HEADERS - set(header_index)
    if missing:
        raise ValueError(
            "Dosyada şu zorunlu sütunlar eksik: " + ", ".join(sorted(missing))
        )

    def get(row_cells, header):
        idx = header_index.get(header)
        if idx is None or idx >= len(row_cells):
            return None
        return row_cells[idx].value

    results = []
    created_count = 0
    error_count = 0

    for row_number, row_cells in enumerate(ws.iter_rows(min_row=2), start=2):
        if all(cell.value in (None, "") for cell in row_cells):
            continue  # tamamen boş satırı atla

        ad = _cell_text(get(row_cells, "Ad"))
        soyad = _cell_text(get(row_cells, "Soyad"))
        team_name = _cell_text(get(row_cells, "Ekip Adı"))
        team_city = _cell_text(get(row_cells, "Ekip Şehri"))
        email = _cell_text(get(row_cells, "E-posta"))
        phone = _cell_text(get(row_cells, "Telefon"))
        birth_date_raw = get(row_cells, "Doğum Tarihi")
        joined_at_raw = get(row_cells, "Katılma Tarihi")
        username = _cell_text(get(row_cells, "Kullanıcı Adı"))

        row_errors = []
        if not ad:
            row_errors.append("Ad boş olamaz.")
        if not soyad:
            row_errors.append("Soyad boş olamaz.")

        team = _resolve_team(team_name, team_city, row_errors)

        birth_date_val = _parse_date(birth_date_raw)
        if birth_date_raw not in (None, "") and birth_date_val is None:
            row_errors.append(f"Doğum Tarihi anlaşılamadı: '{birth_date_raw}' (GG.AA.YYYY kullanın).")

        joined_at_val = _parse_date(joined_at_raw)
        if joined_at_raw not in (None, "") and joined_at_val is None:
            row_errors.append(f"Katılma Tarihi anlaşılamadı: '{joined_at_raw}' (GG.AA.YYYY kullanın).")
        if joined_at_val is None:
            joined_at_val = timezone.localdate()

        if row_errors:
            results.append({
                "row": row_number, "ad": ad, "soyad": soyad, "status": "error",
                "message": " ".join(row_errors), "username": username, "password": None,
            })
            error_count += 1
            continue

        try:
            with transaction.atomic():
                generated_password = None
                if username:
                    user, user_created = User.objects.get_or_create(
                        username=username,
                        defaults={
                            "first_name": ad, "last_name": soyad, "email": email,
                            "phone_number": phone, "birth_date": birth_date_val,
                        },
                    )
                    if not user_created:
                        # Mevcut kullanıcı: sadece boş alanları doldur, var olanı ezme.
                        changed = False
                        if email and not user.email:
                            user.email = email
                            changed = True
                        if phone and not user.phone_number:
                            user.phone_number = phone
                            changed = True
                        if birth_date_val and not user.birth_date:
                            user.birth_date = birth_date_val
                            changed = True
                        if changed:
                            user.save()
                else:
                    username = _slugify_username(ad, soyad)
                    generated_password = _generate_password()
                    user = User.objects.create_user(
                        username=username, first_name=ad, last_name=soyad,
                        email=email, password=generated_password,
                    )
                    user.phone_number = phone
                    user.birth_date = birth_date_val
                    user.save()
                    user_created = True

                existing_membership = TeamMembership.objects.filter(
                    user=user, team=team, left_at__isnull=True
                ).first()
                if existing_membership:
                    results.append({
                        "row": row_number, "ad": ad, "soyad": soyad, "status": "skipped",
                        "message": f"{user.username} zaten '{team}' ekibinde (aktif üyelik var).",
                        "username": user.username, "password": None,
                    })
                    continue

                TeamMembership.objects.create(user=user, team=team, joined_at=joined_at_val)

                results.append({
                    "row": row_number, "ad": ad, "soyad": soyad,
                    "status": "created" if user_created else "added",
                    "message": (
                        f"Yeni hesap oluşturuldu ve '{team}' ekibine eklendi."
                        if user_created else f"Mevcut hesap '{team}' ekibine eklendi."
                    ),
                    "username": user.username, "password": generated_password,
                })
                created_count += 1
        except Exception as exc:  # savunma amaçlı: beklenmeyen satır hatası tüm dosyayı düşürmesin
            results.append({
                "row": row_number, "ad": ad, "soyad": soyad, "status": "error",
                "message": f"Beklenmeyen hata: {exc}", "username": username, "password": None,
            })
            error_count += 1

    return {"rows": results, "created_count": created_count, "error_count": error_count}
