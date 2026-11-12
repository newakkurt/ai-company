# New Akkurt AI Company

Bağımsız, modüler, 14 rol ajanlı ve insan-onaylı AI şirketi orkestrasyon çatısı.

## Neler var?
- 14 uzman rol: CEO, proje yönetimi, teknoloji mimarisi, yazılım, network/altyapı, araştırma, pazarlama, içerik, ürün/iş, veri, hafıza, QA, güvenlik ve CFO/finans operasyonları.
- SQLite görev, ajan ataması, analiz çıktısı ve denetim kaydı.
- Yerel bilgi hafızası: `remember` / `recall`.
- Şeffaf anahtar-kelime yönlendirmesi ve isteğe bağlı yerel Ollama modeli.
- İsteğe bağlı, izin listeli Telegram görev alımı.
- Otonom günlük/haftalık görev üretici, web araştırması (kaynaklı), satış ve rapor bildirimleri (Telegram), gelen mail için taslak/cevap altyapısı. Kurulum: [docs/AUTONOMY_SETUP.md](docs/AUTONOMY_SETUP.md)

**Önemli:** 14 rol tanımlı ve yerel modelle analiz yapabilecek altyapı hazırdır. Model bağlı değilken ajanlar arka planda bağımsız çalışan servisler değildir. Görev yönlendirme deterministiktir; LLM çıktıları öneridir, doğrulanmış gerçek değildir.

## Ücretsiz / yerel öncelikli
Python + SQLite + isteğe bağlı Ollama. Bulut LLM API anahtarı zorunlu değildir. Yerel modelin çalışması için Ollama ve seçilen modelin bilgisayara kurulması gerekir.

## Güvenlik
- Varsayılan mod `dry_run`.
- Ajanlar shell komutu çalıştırmaz, cihazlara bağlanmaz, kodu otomatik değiştirmez.
- Yayın, deploy, harcama, veri silme, Git yazma/PR ve network cihaz değişiklikleri ayrı, kapsamı açık insan onayı ister.
- Onay kaydı kendi başına işlem yürütmez.
- Telegram yalnızca `TELEGRAM_ALLOWED_CHAT_IDS` listesindeki sohbetlerden görev alır.
- Gizli anahtarlar repoya veya loglara yazılmaz.
- Mevcut projeler ayrı depolarda kalır; kodları bu repoya kopyalanmaz.

## Windows kurulumu (PowerShell)
Python 3.10+ ve Git gerekir.

```powershell
git clone https://github.com/newakkurt/ai-company.git
cd ai-company
git checkout main

py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
python -m company.cli doctor
python -m company.cli agents
```

PowerShell sanal ortam aktivasyonunu engellerse yalnızca açık terminal oturumunda:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## İlk komutlar
```powershell
python -m company.cli agents
python -m company.cli plan "Huawei switch SNMP network audit"
python -m company.cli plan --all-agents "Şirket genel strateji ve proje denetimi"
python -m company.cli list
python -m company.cli remember "Network lab" "Huawei SNMP test notları" --tags "network,huawei,snmp"
python -m company.cli recall "Huawei SNMP"
```

`plan` görev oluşturur ve uzman rol önerileri kaydeder; henüz model analizi yapmaz.

## Yerel AI modeli (isteğe bağlı)
1. Windows'a Ollama kur ve çalıştır.
2. PowerShell'de bir model indir: `ollama pull qwen2.5:7b`.
3. İsteğe bağlı ayarları proje kökündeki `.env` dosyasında tanımla; CLI bu dosyayı otomatik yükler (mevcut Windows ortam değişkenlerini ezmez):
```powershell
$env:AI_COMPANY_OLLAMA_URL = "http://127.0.0.1:11434"
$env:AI_COMPANY_OLLAMA_MODEL = "qwen2.5:7b"
``
4. Önce `plan` ile görev oluştur, ekrana yazılan task ID'yi kullan:
```powershell
python -m company.cli run task-XXXXXXXXXX
``
Bu komut CEO ve yönlendirilen uzman roller için yerel modelden analiz alır ve SQLite'a kaydeder. Analiz dışında hiçbir işlem yapmaz. Model bilgisayarın RAM/VRAM kapasitesine göre seçilmelidir.

## Telegram görev alımı
1. BotFather üzerinden ayrı bir AI Company botu oluştur.
2. Token'ı yerel `.env` dosyasına koy; GitHub'a veya sohbete gönderme.
3. `TELEGRAM_BOT_TOKEN` değerini ortam değişkeni olarak yükle ve botuna `/start` gönder.
4. `python -m company.cli telegram-id` ile bekleyen mesajlardan chat ID'ni al. Bu komut mesaj metnini göstermez.
5. Chat ID'ni `TELEGRAM_ALLOWED_CHAT_IDS` değişkenine ekle.
6. `python -m company.cli telegram-poll` komutunu çalıştır.
7. Telegram'da `/task Görev açıklaması` gönder.

Bot polling çalışırken makine ve internet bağlantısı açık kalmalıdır. Telegram botu görevleri yalnızca SQLite'a kaydeder.

## Testler
```powershell
python -m unittest discover -s tests -v
```
GitHub Actions ayrıca Python 3.10, 3.11 ve 3.12 üzerinde testleri çalıştırır.

## Bulut paneli (Render)

Bu sürüm FastAPI tabanlı bir panel ve korumalı görev API'si içerir:
- Render başlangıç komutu: `uvicorn app:app --host 0.0.0.0 --port $PORT`
- Sağlık kontrolü: `/healthz`
- Panel: ana sayfa
- API: `/api/agents`, `/api/tasks`, `/api/tasks/{id}/run`
- Sunucuda `AI_COMPANY_API_KEY` tanımlanmadan yönetim API'si kapalıdır.
- Bulut modeli için Render ortam değişkenlerine `GEMINI_API_KEY` eklenmelidir. Anahtarı GitHub'a veya sohbet mesajına koyma.
- İsteğe bağlı model adı: `AI_COMPANY_GEMINI_MODEL=gemini-2.5-flash`.
- 14 rol bir göreve atanabilir; `run` analiz üretir, dış işlem yapmaz.

**Kalıcı veri:** Render üzerinde `SUPABASE_URL`, `SUPABASE_ANON_KEY` ve yalnızca sunucuda tutulan `SUPABASE_DB_GATE_KEY` tanımlıysa görevler ayrı Supabase PostgreSQL veritabanına yazılır. Bu projede RLS açık, özel anahtar kontrolü sunucu tarafında yapılır. Yerel geliştirmede SQLite geri dönüşü korunur.

**Render ortam değişkenleri**
- `AI_COMPANY_API_KEY`: Panel/API erişim anahtarı.
- `SUPABASE_URL`: AI Company'ye özel Supabase proje URL'si.
- `SUPABASE_ANON_KEY`: Bu projeye ait public anon key.
- `SUPABASE_DB_GATE_KEY`: Veritabanı pre-request doğrulaması için gizli sunucu anahtarı; istemciye veya Git'e koyma.
- `GEMINI_API_KEY`: Bulut analizleri için Gemini anahtarı. Bu değişken eklenmeden ajan analizi başlatılamaz.
- `AI_COMPANY_GEMINI_MODEL`: İsteğe bağlı model seçimi (varsayılan `gemini-2.5-flash`).

NetCmd projesi/veritabanı kullanılmaz. Supabase Free projeleri 500 MB veritabanı kotası ve düşük aktivitede otomatik duraklatma sınırlamalarına tabidir.

## Dokümantasyon
- [NetCmd PRO satış, Buy Me a Coffee webhook ve banka mutabakatı](docs/SALES_AND_BILLING.md)
- [14 ajan işletim modeli](docs/AGENTS.md)
- [Mimari](docs/ARCHITECTURE.md)
- [Güvenlik](docs/SECURITY.md)
- [Yol haritası](docs/ROADMAP.md)
- [Sahip delegasyonu ve otonom çalışma modeli](docs/OWNER_DELEGATION_AND_AUTONOMY.md)


## Dijital ürün fabrikası

Yönetim API'si üzerinden ürün fabrikası uçları:
- `GET /api/factory/status`: pipeline ve güvenlik sınırları.
- `POST /api/factory/research`: 14 rol içinden araştırma, ürün, pazarlama, mimari, network, güvenlik ve QA rollerine kanıtlı pazar araştırması görevi açar.
- `POST /api/factory/score`: 7 ölçütlü, ağırlıkları açık 0-100 fırsat puanı ve güvenlik riski cezası.
- `POST /api/factory/build`: Python API, web uygulaması veya Python CLI MVP kaynakları, README, örnek veri, test planı, QA/güvenlik raporu ve sürümlü ZIP üretir.
- `GET /api/factory/products/{product_id}`: sürüm manifesti ve kalite özeti.
- `GET /api/factory/products/{product_id}/download`: ZIP teslimi.

Tüm uçlar `Authorization: Bearer <AI_COMPANY_API_KEY>` gerektirir. Örnek:
```json
{"name":"NetOps Mini Audit","description":"Küçük MSP ekipleri için çok üreticili switch envanteri ve salt-okunur konfigürasyon denetimi MVP'si","product_type":"python_api","version":"0.1.0"}
```

**Güvenlik ve teslimat notları:** Üretilen kaynak kod hiçbir zaman worker içinde çalıştırılmaz. Dosya yolu/uzantısı/boyutu ve gömülü sırlar doğrulanır; Python sözdizimi AST ile kontrol edilir; riskli kalıplar uyarı üretir. Bunlar tam runtime testi veya güvenlik sertifikası değildir. Her sürüm için SHA-256 ve yerel yedek ZIP oluşturulur. Render Free dosya sistemi geçicidir; ZIP'i kalıcı müşteri teslimi olarak kullanmadan önce kalıcı object storage/harici release deposu bağlanmalıdır. Ürünler varsayılan olarak `review_required` durumundadır.


## Müşteri bulma ve CRM

CRM ekranı: `/crm` (API anahtarı gerekir). Özellikler:
- Türkiye ve global prospect araştırması için ajan görevi oluşturma; günlük prospect playbook çıktıları JSON bloklarından CRM'e alınır.
- Şirketleri ülke + normalize şirket adı ile tekilleştirme; kamuya açık kaynak URL'si, kaynak adı, sektör, ihtiyaç ve uyum gerekçesi kaydı.
- 0–100 açıklanabilir müşteri uygunluk puanı; şirket/kişi kaynak kayıtları.
- Kişi kaydı, satış aşamaları, teklif taslağı ve takip tarihi.
- Gelen kutusu mesaj sınıflandırma kaydı; hassas konular insan incelemesine ayrılır.
- Merkezi unsubscribe/do-not-contact listesi; gelen ret isteği gelecekteki iletişimi engeller.
- E-posta cevapları yalnızca `MAIL_KNOWLEDGE` içindeki sahip-onaylı bilgilerle hazırlanır. Bilgi tabanı boşsa otomatik yanıt gönderimi engellenir.
- CRM prospect teklifleri yalnızca taslak olarak oluşturulur. Soğuk e-posta gönderimi kapalıdır; insan onayı ve geçerli iletişim izni/hukuki dayanak olmadan gönderim yapılmaz.

CRM tabloları Supabase'te RLS + mevcut özel `app.ai_company_authorized` gate ile korunur. Kişisel veri yerine mümkün olduğunca şirketin yayımladığı genel iletişim kanalları kullanılmalıdır. Türkiye'de ticari elektronik ileti ve İYS yükümlülükleri, GDPR/KVKK ve veri saklama süreleri şirket tarafından doğrulanmalıdır. Sistem hukuki dayanak veya rıza varlığını kendiliğinden varsaymaz.
