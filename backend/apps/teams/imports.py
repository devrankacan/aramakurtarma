"""Excel'den (.xlsx) toplu ekip üyesi içe aktarma.

Kullanım: admin panelinde Ekip Üyelikleri -> İçe Aktar. Sütun başlıkları
isimle eşleştirilir (sıra önemli değil, yaygın yazım farklılıkları --
boşluk/nokta/büyük-küçük harf -- tolere edilir). Desteklenen başlıklar
için TEMPLATE_HEADERS ve HEADER_SYNONYMS'e bakın. Şablon, derneğin resmi
"Personel Manifestosu" formundaki başlıklarla uyumludur.

Başlık satırı dosyanın ilk satırı olmak zorunda değil -- üstte başlık/
tarih gibi satırlar olsa bile ilk ~25 satır taranıp en çok tanınan sütunu
içeren satır başlık satırı kabul edilir (bkz. _find_header_row).

İsim: "Adı Soyadı" tek sütun olarak verilebilir (son kelime soyad kabul
edilir) ya da ayrı "Ad" + "Soyad" sütunları kullanılabilir.

Ekip: dosyada "Ekip Adı" sütunu yoksa/boşsa, içe aktarma formunda seçilen
"Hedef Ekip" kullanılır. İkisi de yoksa satır hata olarak işaretlenir.

Hassas alanlar: "T.C. Kimlik No" ve "Engel Durumu" UserHealthProfile'a
şifrelenerek yazılır (sadece superuser görebilir, erişim kayıt altına
alınır) -- User modeline veya düz metin olarak HİÇBİR YERE yazılmaz.

"Görevi" sütunu sistemdeki Rol kataloğuyla (apps.teams.models.Role) isim
bazında eşleştirilir; eşleşirse UserTeamRole kaydı oluşturulur, eşleşmezse
satır bilgi notuyla (hata değil) işaretlenir.
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

from apps.accounts.models import UserHealthProfile
from apps.teams.models import Role, Team, TeamMembership, UserTeamRole

User = get_user_model()

# Derneğin resmi "Personel Manifestosu" formundaki sütun başlıklarıyla
# uyumlu şablon (SIRA hariç -- o sadece satır numarası, gerekmiyor).
TEMPLATE_HEADERS = [
    "İli",
    "Adı Soyadı",
    "T.C. Kimlik No",
    "Doğum Tarihi",
    "Kan Grubu",
    "Engel Durumu",
    "GSM (Telefon)",
    "E-Posta",
    "Pasaport Bilgileri",
    "Ehliyet",
]
TEMPLATE_EXAMPLE_ROW = [
    "İstanbul",
    "Ayşe Yılmaz",
    "12345678901",
    "15.03.1995",
    "0 RH (+)",
    "YOK",
    "0555 000 00 00",
    "ayse.yilmaz@example.com",
    "YOK",
    "B",
]

# Kanonik alan adı -> kabul edilen başlık yazımları. Eşleştirme sırasında
# boşluk/nokta silinip küçük harfe çevrilir, bu yüzden "T.C. Kimlik No" ile
# "TC Kimlik No" ya da "ADI SOYADI" ile "Adı Soyadı" aynı kabul edilir.
HEADER_SYNONYMS = {
    "full_name": ["Adı Soyadı", "Ad Soyad", "Adı ve Soyadı"],
    "ad": ["Ad"],
    "soyad": ["Soyad"],
    "national_id": ["T.C. Kimlik No", "TC Kimlik No", "T.C. Kimlik Numarası", "TC Kimlik Numarası"],
    "birth_date": ["Doğum Tarihi"],
    "blood_type": ["Kan Grubu"],
    "disability_status": ["Engel Durumu"],
    "occupation": ["Mesleği", "Meslek"],
    "duty": ["Görevi", "Görev"],
    "phone": ["Telefon Numarası", "Telefon", "GSM (Telefon)", "GSM"],
    "relative_phone": ["Yakınının Telefonu", "Yakını Telefonu", "Acil Durum Telefonu"],
    "email": ["e-posta", "E-posta", "Eposta", "Email", "E-mail"],
    "passport_info": ["Pasaport Bilgileri", "Pasaport"],
    "driving_license": ["Ehliyet"],
    "address": ["Adres"],
    "team_name": ["Ekip Adı"],
    "team_city": ["Ekip Şehri", "İli", "İl"],
    "joined_at": ["Katılma Tarihi"],
    "username": ["Kullanıcı Adı"],
}

_TR_LOWER_MAP = str.maketrans({"İ": "i", "I": "ı"})
_TR_ASCII_MAP = str.maketrans({
    "ç": "c", "Ç": "c", "ğ": "g", "Ğ": "g", "ı": "i", "I": "i", "İ": "i",
    "ö": "o", "Ö": "o", "ş": "s", "Ş": "s", "ü": "u", "Ü": "u",
})
_BLOOD_TYPE_RE = re.compile(r"^(0|AB|A|B)RH?\(?([+-])\)?$")


def _normalize_header(text):
    text = (text or "").translate(_TR_LOWER_MAP).lower()
    return re.sub(r"[\s.]+", "", text)


def _build_header_lookup():
    """normalize edilmiş başlık metni -> kanonik alan adı."""
    lookup = {}
    for canonical, synonyms in HEADER_SYNONYMS.items():
        for syn in synonyms:
            lookup[_normalize_header(syn)] = canonical
    return lookup


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
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
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


def _parse_blood_type(text):
    """'0 RH (-)' / 'AB RH (+)' / 'A RH(+)' gibi yazımları modelin
    beklediği '0-' / 'AB+' / 'A+' biçimine çevirir. Ayrıştırılamazsa
    boş döner."""
    if not text:
        return ""
    compact = text.upper().translate(_TR_LOWER_MAP)
    compact = re.sub(r"\s+", "", compact)
    match = _BLOOD_TYPE_RE.match(compact)
    if not match:
        return ""
    group, sign = match.groups()
    return f"{group}{sign}"


def _split_full_name(full_name):
    parts = full_name.split()
    if len(parts) < 2:
        return full_name, ""
    return " ".join(parts[:-1]), parts[-1]


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


def _fill_blank_fields(user, fields):
    """Mevcut kullanıcının sadece BOŞ alanlarını doldurur, var olan veriyi
    ezmez. fields: {alan_adı: yeni_değer}."""
    changed = False
    for field_name, new_value in fields.items():
        if new_value and not getattr(user, field_name):
            setattr(user, field_name, new_value)
            changed = True
    if changed:
        user.save()


def _resolve_team(team_name, team_city, default_team, row_errors):
    if not team_name:
        if default_team is not None:
            return default_team
        row_errors.append(
            "Ekip Adı boş ve içe aktarma formunda 'Hedef Ekip' seçilmemiş."
        )
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


def _find_header_row(ws, header_lookup, max_scan_rows=25):
    """Başlık satırı dosyanın ilk satırı olmayabilir (üstte logo/başlık/
    tarih satırları olabilir) -- ilk max_scan_rows satır taranıp en çok
    tanınan sütun başlığını içeren satır seçilir."""
    best_row_number = None
    best_match_count = 0
    for row_number, row in enumerate(ws.iter_rows(min_row=1, max_row=max_scan_rows), start=1):
        matched = set()
        for cell in row:
            canonical = header_lookup.get(_normalize_header(_cell_text(cell.value)))
            if canonical:
                matched.add(canonical)
        if len(matched) > best_match_count:
            best_match_count = len(matched)
            best_row_number = row_number
    return best_row_number, best_match_count


def parse_and_import(uploaded_file, default_team=None):
    """Excel dosyasını okuyup satır satır işler. Her satır kendi
    transaction'ında; bir satırdaki hata diğerlerini etkilemez.
    default_team: dosyada Ekip Adı boş bırakılan satırlar için kullanılacak
    ekip (içe aktarma formundaki 'Hedef Ekip' seçimi).
    Dönüş: {"rows": [...], "created_count": int, "error_count": int}."""
    wb = openpyxl.load_workbook(uploaded_file, data_only=True)
    ws = wb.active

    header_lookup = _build_header_lookup()
    header_row_number, match_count = _find_header_row(ws, header_lookup)
    if header_row_number is None or match_count < 2:
        raise ValueError(
            "Dosyada tanınan bir başlık satırı bulunamadı. Sütun başlıklarının "
            "şablon dosyasındaki gibi olduğundan emin olun."
        )

    raw_headers = [_cell_text(cell.value) for cell in next(ws.iter_rows(
        min_row=header_row_number, max_row=header_row_number
    ))]
    field_index = {}
    for idx, raw in enumerate(raw_headers):
        canonical = header_lookup.get(_normalize_header(raw))
        if canonical:
            field_index[canonical] = idx

    has_name_field = "full_name" in field_index or ("ad" in field_index and "soyad" in field_index)
    if not has_name_field:
        raise ValueError(
            "Dosyada isim sütunu bulunamadı. 'Adı Soyadı' tek sütun olarak ya da "
            "ayrı 'Ad' + 'Soyad' sütunları olarak eklenmeli."
        )

    def get(row_cells, field):
        idx = field_index.get(field)
        if idx is None or idx >= len(row_cells):
            return None
        return row_cells[idx].value

    results = []
    created_count = 0
    error_count = 0

    for row_number, row_cells in enumerate(
        ws.iter_rows(min_row=header_row_number + 1), start=header_row_number + 1
    ):
        if all(cell.value in (None, "") for cell in row_cells):
            continue  # tamamen boş satırı atla

        if "full_name" in field_index:
            ad, soyad = _split_full_name(_cell_text(get(row_cells, "full_name")))
        else:
            ad = _cell_text(get(row_cells, "ad"))
            soyad = _cell_text(get(row_cells, "soyad"))

        national_id = _cell_text(get(row_cells, "national_id"))
        blood_type_raw = _cell_text(get(row_cells, "blood_type"))
        disability_status = _cell_text(get(row_cells, "disability_status"))
        occupation = _cell_text(get(row_cells, "occupation"))
        duty = _cell_text(get(row_cells, "duty"))
        phone = _cell_text(get(row_cells, "phone"))
        relative_phone = _cell_text(get(row_cells, "relative_phone"))
        email = _cell_text(get(row_cells, "email"))
        passport_info = _cell_text(get(row_cells, "passport_info"))
        driving_license = _cell_text(get(row_cells, "driving_license"))
        address = _cell_text(get(row_cells, "address"))
        team_name = _cell_text(get(row_cells, "team_name"))
        team_city = _cell_text(get(row_cells, "team_city"))
        birth_date_raw = get(row_cells, "birth_date")
        joined_at_raw = get(row_cells, "joined_at")
        username = _cell_text(get(row_cells, "username"))

        # "İli" hem Ekip Şehri hem de kişinin ilini temsil edebilir; eğer
        # ayrıca gerçek bir "Ekip Adı" sütunu yoksa bunu ekip belirlemede
        # kullanmayız (tek ekiplik dosyalarda yanlış eşleşmeyi önler) --
        # sadece "Ekip Adı" ile birlikte netleştirme amacıyla kullanılır.
        if "team_name" not in field_index:
            team_city = ""

        row_errors = []
        row_notes = []
        if not ad:
            row_errors.append("Ad boş olamaz.")
        if not soyad:
            row_errors.append("Soyad boş olamaz.")

        team = _resolve_team(team_name, team_city, default_team, row_errors)

        birth_date_val = _parse_date(birth_date_raw)
        if birth_date_raw not in (None, "") and birth_date_val is None:
            row_errors.append(f"Doğum Tarihi anlaşılamadı: '{birth_date_raw}' (GG.AA.YYYY kullanın).")

        joined_at_val = _parse_date(joined_at_raw)
        if joined_at_raw not in (None, "") and joined_at_val is None:
            row_errors.append(f"Katılma Tarihi anlaşılamadı: '{joined_at_raw}' (GG.AA.YYYY kullanın).")
        if joined_at_val is None:
            joined_at_val = timezone.localdate()

        if national_id and (not national_id.isdigit() or len(national_id) != 11):
            row_notes.append("T.C. Kimlik No 11 haneli bir sayı gibi görünmüyor, olduğu gibi kaydedildi.")

        blood_type = _parse_blood_type(blood_type_raw)
        if blood_type_raw and not blood_type:
            row_notes.append(f"Kan Grubu anlaşılamadı: '{blood_type_raw}', boş bırakıldı.")

        role = None
        if duty:
            role = Role.objects.filter(name__iexact=duty).first()
            if role is None:
                row_notes.append(f"'{duty}' rolü sistemde tanımlı değil, rol ataması yapılmadı.")

        if row_errors:
            results.append({
                "row": row_number, "ad": ad, "soyad": soyad, "status": "error",
                "message": " ".join(row_errors), "username": username, "password": None,
            })
            error_count += 1
            continue

        optional_fields = {
            "email": email, "phone_number": phone, "birth_date": birth_date_val,
            "occupation": occupation, "driving_license": driving_license,
            "passport_info": passport_info, "address": address,
        }

        try:
            with transaction.atomic():
                generated_password = None
                if username:
                    user, user_created = User.objects.get_or_create(
                        username=username,
                        defaults={"first_name": ad, "last_name": soyad, **optional_fields},
                    )
                    if not user_created:
                        _fill_blank_fields(user, optional_fields)
                else:
                    # Kullanıcı Adı verilmemiş: dosyayı ikinci kez (ör. güncellenmiş
                    # bir manifesto) yüklediğinizde aynı kişiye ikinci hesap
                    # açılmasın diye ad+soyad'a göre mevcut kullanıcı aranır.
                    name_matches = list(
                        User.objects.filter(first_name__iexact=ad, last_name__iexact=soyad)
                    )
                    if len(name_matches) == 1:
                        user = name_matches[0]
                        user_created = False
                        _fill_blank_fields(user, optional_fields)
                    else:
                        if len(name_matches) > 1:
                            row_notes.append(
                                f"Aynı isimde ({ad} {soyad}) birden fazla mevcut kullanıcı "
                                f"bulundu, karışıklığı önlemek için yeni hesap oluşturuldu."
                            )
                        username = _slugify_username(ad, soyad)
                        generated_password = _generate_password()
                        user = User.objects.create_user(
                            username=username, first_name=ad, last_name=soyad,
                            email=email, password=generated_password,
                        )
                        for field_name, new_value in optional_fields.items():
                            if field_name != "email":
                                setattr(user, field_name, new_value)
                        user.save()
                        user_created = True

                if national_id or relative_phone or blood_type or disability_status:
                    profile, _ = UserHealthProfile.objects.get_or_create(user=user)
                    profile_changed = False
                    for field_name, new_value in (
                        ("national_id", national_id),
                        ("emergency_contact_phone", relative_phone),
                        ("blood_type", blood_type),
                        ("disability_status", disability_status),
                    ):
                        if new_value and not getattr(profile, field_name):
                            setattr(profile, field_name, new_value)
                            profile_changed = True
                    if profile_changed:
                        profile.save()

                if role is not None:
                    UserTeamRole.objects.get_or_create(user=user, team=team, role=role)

                existing_membership = TeamMembership.objects.filter(
                    user=user, team=team, left_at__isnull=True
                ).first()
                if existing_membership:
                    results.append({
                        "row": row_number, "ad": ad, "soyad": soyad, "status": "skipped",
                        "message": " ".join(
                            [f"{user.username} zaten '{team}' ekibinde (aktif üyelik var)."] + row_notes
                        ),
                        "username": user.username, "password": None,
                    })
                    continue

                TeamMembership.objects.create(user=user, team=team, joined_at=joined_at_val)

                base_message = (
                    f"Yeni hesap oluşturuldu ve '{team}' ekibine eklendi."
                    if user_created else f"Mevcut hesap '{team}' ekibine eklendi."
                )
                results.append({
                    "row": row_number, "ad": ad, "soyad": soyad,
                    "status": "created" if user_created else "added",
                    "message": " ".join([base_message] + row_notes),
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
