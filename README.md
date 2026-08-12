# Arama Kurtarma Operasyon ve Koordinasyon Platformu

İyilik Derneği arama kurtarma birimi için operasyon/koordinasyon platformu.

## Stack

- Backend: Django + Django REST Framework + Channels (ASGI/WebSocket)
- DB: PostgreSQL (PostGIS uzantılı imaj — ileride konum bazlı sevk/ihbar için)
- Cache/Channel layer: Redis
- Reverse proxy: Nginx
- Çalışma ortamı: Docker + docker-compose (sunucu/subdomain değişiminde taşınabilirlik için)

## Modüler yapı

Her ana başlık ayrı bir Django app'i (`backend/apps/`):

| App | Kapsam | Durum |
|---|---|---|
| `accounts` | Kullanıcı modeli | Kuruldu |
| `teams` | Şube/Ekip hiyerarşisi, rol/yetki | Kuruldu |
| `accreditation` | Akreditasyon seviyeleri, kişisel sertifikalar | Kuruldu |
| `inventory` | Envanter, akreditasyon-bazlı zorunlu ekipman, zimmet | Kuruldu |
| `dispatch` | İhbar, sevk, canlı saha durumu | Yer tutucu (sonraki tur) |
| `calendar_app` | Birim bazlı görünürlükli etkinlik takvimi | Yer tutucu (sonraki tur) |
| `forms_app` | Dijital formlar, KVKK özel nitelikli veri şifreleme | Yer tutucu (sonraki tur) |
| `notifications` | Dinamik filtre + toplu SMS/bildirim | Yer tutucu (sonraki tur) |

## Yerel geliştirme

```bash
cp .env.example .env   # değerleri kendi ortamına göre düzenle
docker compose up --build
```

Backend: http://localhost/ (nginx üzerinden), admin paneli: http://localhost/admin/

İlk kurulumda:

```bash
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py createsuperuser
```

## Sunucu değişimi / subdomain ekleme

Domain/host bilgisi koda gömülü değil, `.env` üzerinden okunuyor:

- `SERVER_NAME` → nginx `server_name` (subdomain değişince tek satır)
- `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` → Django tarafı

Yeni sunucuya taşırken: repoyu çek, `.env` dosyasını yeni ortama göre doldur,

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

## Notlar

- `AUTH_USER_MODEL` proje başında özelleştirildi (`accounts.User`) — sonradan değiştirmek zor olduğu için baştan yapıldı.
- Kritik tablolarda (`TeamMembership`, `UserTeamRole`, `AccreditationRecord`, `CustodyAssignment`) `django-simple-history` ile denetim/izleme kaydı tutuluyor.
- `DJANGO_ENV=dev|prod` ortam değişkeni ile `backend/config/settings/{dev,prod}.py` arasında geçiş yapılıyor.
