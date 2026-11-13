# Otonom çalışma ve worker kurulumu

Bu sistem görevleri otomatik üretir ve araştırma/analiz/ürün taslağı işlemlerini worker üzerinden yürütür. Ancak gerçek satış ve yayın için ödeme, onay, teslimat ve yasal kontrollerin tamamlanması gerekir.

## Scheduler davranışı

- 14 uzman rol vardır; 14 ayrı sunucu/model instance'ı değildir.
- Scheduler günde iki sınırlı iş akışı seçer: günlük odak + haftalık/ikinci iş akışı.
- İş akışları dönüşümlüdür: müşteri araştırması, ürün fırsatı, ürün fabrikası, SEO, LinkedIn, YouTube, Instagram, Telegram, görsel brief, e-posta kampanyası taslağı, dönüşüm analizi ve haftalık büyüme raporu.
- Haftalık ürün fabrikası tek bir küçük offline-first Python API starter ZIP üretir.
- Görev kimlikleri tarih/hafta bazlıdır; tekrar seed edilmez.
- Kota hatalarında Groq varsa 30 dakika bekleme ve en fazla 3 deneme; Groq yoksa 24 saat bekleme ve en fazla 3 deneme. Diğer hatalarda en fazla 2 retry.
- Ürün, müşteri ve gelir verisi yoksa ajanlar bunu açıkça belirtir; sayı uydurmaz.

## Worker seçimi

Aktif tercih GitHub Actions scheduled worker'dır:
- `.github/workflows/agent-worker.yml` her 5 dakikada bir çalışır.
- Her çalışmada en fazla bir task işler; GitHub concurrency aynı workflow çalıştırmalarını sıraya alır. Render embedded worker kapalıdır; ikinci consumer yoktur.
- Repository secrets: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_DB_GATE_KEY`, `GROQ_API_KEY` (Gemini opsiyoneldir).
- Son doğrulanan Actions ortamında Groq doğrudan seçildi (`openai/gpt-oss-20b`); kopyalanan anahtarlardaki boşluk/çift tırnak normalize edilir. CEO agent smoke test'i gerçek çıktı üreterek tamamlandı.
- Render web servisi `AI_COMPANY_EMBEDDED_WORKER=false` ile API/dashboard olarak kalır.

Render embedded worker yalnızca bilinçli geçişte kullanılmalıdır:
- `AI_COMPANY_EMBEDDED_WORKER=true` Render üzerinde ikinci consumer başlatır.
- Bu moda geçmeden önce GitHub Actions schedule kapatılmalı; iki consumer aynı anda açılmamalıdır.
- Render Free uyur/yeniden başlar; kesintisiz 7/24 garantisi vermez.
- Uzun LLM çağrılarında worker task heartbeat gönderir; 15 dakikalık stale lease yalnızca worker gerçekten durmuşsa devreye girmelidir.

## Render temel değişkenleri

```text
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_DB_GATE_KEY=
AI_COMPANY_API_KEY=
GEMINI_API_KEY=   # veya GROQ_API_KEY
AI_COMPANY_GEMINI_MODEL=gemini-3.5-flash-lite
AI_COMPANY_AUTO_TASKS=true
AI_COMPANY_EMBEDDED_WORKER=false
TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_CHAT_IDS=
TELEGRAM_OWNER_CHAT_ID=
AI_COMPANY_EMBEDDED_TELEGRAM=false
```

## CRM ve müşteri bulma

- Ajanlar şirket adaylarını yalnızca açık kaynaklardan araştırır.
- Her kaynak URL'si public HTTPS, DNS/IP pinning, redirect kontrolü ve sınırlı içerik boyutu ile doğrulanır.
- Worker her çalışmada en fazla 5 adet `not_checked` CRM kaynağını kontrol eder. HTTP 200/eşleşme yalnızca kaynak kanıtıdır; şirket kimliği ve hukuki iletişim dayanağı için insan onayı gerekir. Erişilemeyen/çok büyük/eşleşmeyen kayıtlar otomatik `qualified` yapılmaz.
- Sahip CRM ekranında kaynağı ve şirketi kontrol edip "Verify source" yapmadan şirket `qualified` aşamasına geçemez.
- Soğuk e-posta otomatik gönderilmez. Teklifler taslak olarak hazırlanır; iletişim için yasal dayanak ve insan onayı gerekir.

## Mail güvenliği

- Varsayılan `AI_COMPANY_MAIL_MODE=draft`: hiçbir mail gönderilmez.
- `auto_reply` yalnızca gelen destek maillerine yöneliktir; prospect outreach değildir.
- Auto-reply için ilk `Authentication-Results` header'ı `MAIL_TRUSTED_AUTH_SERVERS` listesindeki sunucudan gelmeli, DMARC pass ve SPF veya DKIM pass göstermelidir.
- Gönderim sayacı Supabase/SQLite'ta kalıcıdır; aynı Message-ID ikinci kez gönderilmez.
- Günlük toplam 20, aynı gönderenden günlük 2 cevap sınırı varsayılandır.
- SMTP belirsiz/başarısız olursa otomatik tekrar yapılmaz; sahibine bildirilir.
- Ayrı destek mailbox'ı ve Gmail App Password kullan; ana kişisel mailbox'ı bağlama.

## Ürün fabrikası ve satış

1. Haftalık factory bir ZIP üretir; Supabase'e checksum ile kaydeder, durum `review_required`.
2. Sahip ürünü inceler ve `publish_product) için product_id + SHA-256 kapsamlı onay verir.
3. Onay sonrası `POST /api/factory/products/{product_id}/publish) ürünü satışa hazır yapar.
4. BMC Shop item ID (`extras[].id`), ürün ID ve fiyat `BMC_EXTRA_PRODUCT_MAP ile eşleştirilir.
5. İmzalı live webhook ödeme ledger'ına yazılır ve entitlement oluşturur.
6. Ürün yayınlanmış ve SMTP hazırsa alıcıya 7 gün / 5 indirme limitli link gönderilir. SMTP yoksa sahibine manuel teslimat linki gönderilir.
7. Ürün henüz yayınlanmamışsa entitlement pending kalır; yayın sonrası `POST /api/payments/entitlements/{subscription_id}/deliver) çağrılır.
8. Refund/cancel/pause entitlement erişimini kapatır.

## Canlı doğrulama

`/readyz` worker, model, database ve yalnızca boolean olarak BMC/SMTP/Telegram entegrasyon hazırlığını gösterir. Son denetimde BMC webhook secret, Shop mapping, membership level, SMTP ve Telegram owner notification alanları yapılandırılmamıştı; mail modu `draft`. Gerçek operasyon için ayrıca:
- GitHub Actions son run başarılı olmalı.
- CRM kaynakları kontrol edilmiş olmalı.
- En az bir ürün release QA'dan geçip onaylanmalı.
- BMC test event'inin satış yaratmadığı, kontrollü live event'in bir ledger kaydı ve tek entitlement oluşturduğu doğrulanmalı.
- Gerçek payout ve banka dekontu ayrı ayrı mutabık olmalı.

## Bilinen sınırlar

- Render Free ve ücretsiz model kotası 7/24 kesintisiz çalışmayı garanti etmez.
- Ajanlar dışarıya soğuk satış e-postası atmaz, sosyal medyada otomatik yayın yapmaz ve kullanıcı onayı olmadan ürün yayınlamaz.
- Üretilen ZIP'ler için ağsız runtime sandbox QA henüz tamamlanmalıdır.
- Webhook sale event'i bankaya para geçtiğinin kanıtı değildir.
