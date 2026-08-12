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
| `teams` | Şehir bazlı ekip yönetimi, rol/yetki | Kuruldu |
| `accreditation` | Akreditasyon seviyeleri, kişisel sertifikalar | Kuruldu |
| `inventory` | Envanter, akreditasyon-bazlı zorunlu ekipman, zimmet | Kuruldu |
| `dispatch` | İhbar, sevk, canlı saha durumu | Yer tutucu (sonraki tur) |
| `calendar_app` | Birim bazlı görünürlükli etkinlik takvimi | Yer tutucu (sonraki tur) |
| `forms_app` | Dijital formlar (Gönüllü Başvurusu), KVKK özel nitelikli veri şifreleme | Kuruldu |
| `content` | Bilgi Bankası (PDF), ana sayfa AFAD deprem verisi | Kuruldu |
| `notifications` | Dinamik filtre (Bildirim Grubu) + toplu SMS (NAC) | Kuruldu — NAC API uç noktası doğrulanmayı bekliyor |

## Yerel geliştirme

```bash
cp .env.example .env   # değerleri kendi ortamına göre düzenle
docker compose up --build
```

Backend: http://localhost:$HTTP_PORT/ (nginx üzerinden, `.env`'deki `HTTP_PORT` neyse), admin paneli: http://localhost:$HTTP_PORT/admin/

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

## Paylaşımlı VPS'e kurulum (diğer projeleri etkilememesi için)

Bu proje sunucudaki başka projelerle aynı VPS'i paylaşacaksa:

1. **Boş port bul.** Kuruma başlamadan önce sunucuda hangi portların dolu olduğunu kontrol et:
   ```bash
   sudo ss -tulpn | grep LISTEN
   ```
   Listede görünmeyen bir portu `.env` içindeki `HTTP_PORT` değerine yaz. `db` ve `redis` servisleri zaten host'a hiç port açmıyor (`docker-compose.yml`'de `ports:` tanımlı değil) — sadece proje içi Docker ağında konuşuyorlar, bu yüzden onlarla port çakışması hiç yaşanmaz.
2. **`COMPOSE_PROJECT_NAME`'i benzersiz tut.** `.env` içindeki bu değer container/network/volume adlarının önekidir; farklı projelerin aynı isimde container'ı olsa bile karışmaz, `docker compose down` yalnızca bu projenin kaynaklarını etkiler.
3. **Sunucu genelinde etkili komutlardan kaçın.** `docker system prune`, `docker compose down -v` (başka projenin volume'ünü de silebilecek yanlış dizinde çalıştırılırsa), veya diğer projelerin container'larını `docker stop/rm` ile durdurmak gibi işlemler bu projeye özgü olmayan komutlardır — her zaman bu repo dizininde ve sadece bu projeye ait komutları çalıştır.
4. **İleride subdomain'e bağlarken** sunucuda zaten çalışan bir reverse proxy (nginx/Traefik) varsa, bu projenin nginx'ini host'ta ayrı bir portta (`HTTP_PORT`) tutup, üst seviye reverse proxy'den o porta yönlendirme (`proxy_pass http://127.0.0.1:$HTTP_PORT`) yapman yeterli — bu projenin container'larına dokunman gerekmez.

## Toplu SMS (NAC)

Admin panelde **Bildirim ve Toplu İletişim → Toplu SMS Gönderimleri**'nden:

1. **Toplu SMS Gönderimi ekle** — hedef ekip(ler)i seç (ya da "Tüm Kullanıcılar" işaretle) ve mesaj metnini gir (taslak olarak kaydedilir).
2. Listeden ilgili kaydı seçip **"Seçili taslakları gönder"** aksiyonunu çalıştır.

`.env` içindeki `NAC_SMS_*` değişkenlerini doldurman gerekiyor (`apps/notifications/sms.py`).
**Önemli:** NAC'ın gerçek API uç noktası/istek formatı bu geliştirme ortamından doğrulanamadı
(nac.com.tr ağ politikası tarafından engelliydi) — `sms.py` içindeki istek şekli yaygın SMS API
desenine göre yazıldı ama NAC'ın kendi dokümanıyla karşılaştırılıp gerekirse düzeltilmeli.

## Notlar

- `AUTH_USER_MODEL` proje başında özelleştirildi (`accounts.User`) — sonradan değiştirmek zor olduğu için baştan yapıldı.
- Kritik tablolarda (`TeamMembership`, `UserTeamRole`, `AccreditationRecord`, `CustodyAssignment`) `django-simple-history` ile denetim/izleme kaydı tutuluyor.
- `DJANGO_ENV=dev|prod` ortam değişkeni ile `backend/config/settings/{dev,prod}.py` arasında geçiş yapılıyor.
