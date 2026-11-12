# New Akkurt AI Company

14 uzman rolü kullanan, Supabase tabanlı görev kuyruğu ve insan onay kapılarıyla çalışan AI operasyon sistemi.

**Önemli durum notu:** Bu depo, araştırma/CRM/ürün üretimi/satış teslimatı altyapısını içerir; ancak "kendi kendine müşteri bulup ürün satıp gelir üreten şirket" olarak kabul edilmesi için canlı secrets, Render ayarları, BMC ürün eşlemesi, SMTP teslimatı ve gerçek uçtan uca testlerin tamamlanması gerekir. Üretilen ürünler varsayılan olarak `review_required` durumundadır; sahibin onayı olmadan yayınlanmaz.

## Özellikler

- 14 uzman rol; Gemini birincil, Groq isteğe bağlı kota yedeği.
- Supabase PostgreSQL + RLS + sunucu tarafı API gate; yerel geliştirme için SQLite.
- İdempotent günlük/haftalık iş üretimi: günde iki sınırlı iş akışı, haftalık iş akışları dönüşümlü.
- Tek seferde bir görevi işleyen worker; uzun LLM işlemleri sırasında heartbeat ile lease yenileme.
- Kaynak URL'leri SSRF korumalı HTTPS denetiminden geçen CRM adayları; satış aşamasından önce insan doğrulaması.
- Draft-first e-posta; auto-reply yalnızca güvenilir SPF/DKIM/DMARC sonucu ve kalıcı gönderim limitleriyle.
- Ürün fabrikası: versioned ZIP + SHA-256 + kalıcı saklama.
- Ürün yayını için dosya checksum'una bağlı tek kullanımlık insan onayı.
- BMC webhook, ödeme ledger'ı, ürün entitlement'ı ve süre/indirme limitli güvenli teslimat bağlantısı.
- Telegram bildirimleri, sağlık kontrolü ve görev raporları.

## Yerel kurulum

Python 3.10+:

```powershell
git clone https://github.com/newakkurt/ai-company.git
cd ai-company
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python -m unittest discover -s tests -v
```

Gerçek anahtarları `.env` içine veya Render Environment / GitHub Actions Secrets'a koy; Git'e commit etme.

## Hosted kurulum

### Render environment

Gerekli temel değişkenler:

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_DB_GATE_KEY` (yalnızca sunucu tarafında)
- `AI_COMPANY_API_KEY`
- `GEMINI_API_KEY` veya `GROQ_API_KEY`

İsteğe bağlı hizmetler için Telegram, mail ve BMC değişkenlerini `.env.example` içinden yapılandır.

### GitHub Actions Secrets

`agent-worker.yml` için:

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_DB_GATE_KEY`
- `GEMINI_API_KEY` veya `GROQ_API_KEY`

Worker her 5 dakikada bir en fazla bir görevi işler. Varsayılan tercih budur. Aynı anda iki consumer çalıştırmamak için GitHub Actions schedule açıkken `AI_COMPANY_EMBEDDED_WORKER=false) bırak.

### Worker ve kota

- Scheduler günde iki bounded task seçer; 14 ajanın tamamını her göreve göndermeye çalışmaz.
- Quota hataları 24 saat bekletilir ve en fazla bir kez yeniden denenir.
- Task heartbeat, uzun model çağrılarında 15 dakikalık stale-lease requeue riskini azaltır.
- Render Free uyku/yeniden başlama davranışı nedeniyle 7/24 kesintisiz çalışma garantisi yoktur.

## Ürün yayınlama ve teslimat

Ayrıntılar: [Product publishing and delivery](docs/PRODUCT_PUBLISHING_AND_DELIVERY.md).

1. Ürün fabrikası ZIP üretir ve Supabase'e kaydeder; durum `review_required`.
2. Sahip, `product_id` + `sha256` kapsamıyla `publish_product` onayı oluşturur.
3. Onay sonrası `POST /api/factory/products/{product_id}/publish` çağrılır.
4. BMC level ID, yayınlanmış `product_id` ve fiyat ile `BMC_PRODUCT_LEVEL_MAP` içine eşlenir.
5. İmzalı canlı ödeme webhook'u entitlement oluşturur; SMTP hazırsa alıcıya 7 gün / 5 indirme limitli link gönderilir.
6. Ürün ödeme anında henüz yayınlanmamışsa entitlement pending kalır; yayın sonrası `POST /api/payments/entitlements/{subscription_id}/deliver` ile teslimat tamamlanır.
7. İade/iptal/duraklatma entitlement erişimini kapatır.

## Güvenlik sınırları

- Ajanlar shell, ağ cihazı veya müşteri kimlik bilgilerine erişmez.
- Soğuk satış e-postası otomatik gönderilmez; müşteri iletişimi draft/insan onayı sınırındadır.
- Ürün yayınlama, deployment, para harcama, iade ve diğer kritik dış işlemler açık onay gerektirir.
- Erişilebilir kaynak sayfası tek başına şirketin gerçekliğini kanıtlamaz; CRM'de insan doğrulaması gerekir.
- Ödeme webhook'u satış/üyelik olayıdır; banka mutabakatı veya fatura yerine geçmez.

## Testler

```bash
python -m unittest discover -s tests -v
```

GitHub Actions, Python 3.10 / 3.11 / 3.12 üzerinde testleri çalıştırır.

## Belgeler

- [Architecture](docs/ARCHITECTURE.md)
- [Roadmap and remaining production gates](docs/ROADMAP.md)
- [Autonomy setup](docs/AUTONOMY_SETUP.md)
- [Sales and billing](docs/SALES_AND_BILLING.md)
- [Product publishing and delivery](docs/PRODUCT_PUBLISHING_AND_DELIVERY.md)
- [Security](docs/SECURITY.md)


## Read-only network configuration audit

AI Company includes a file-based audit module for sanitized Cisco, Huawei, and Aruba switch configurations. It does not connect to devices or make changes.

Example commands:

    python -m company.network_audit --input fixtures/network_audit/cisco_sample.cfg --format markdown
    python -m company.network_audit --input fixtures/network_audit/huawei_sample.cfg --format html --output report.html
    python -m company.network_audit --input fixtures/network_audit/aruba_sample.cfg --format json

The report includes evidence lines, severity, recommendations, and limitations. Credential-like values are redacted from report evidence. Review docs/NETWORK_AUDIT_PILOT_SCOPE.md before using customer configurations. This is not a live-device assessment or compliance certification.
