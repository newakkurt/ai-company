# New Akkurt AI Company

Bağımsız, modüler, 14 rol ajanlı ve insan-onaylı AI şirketi orkestrasyon çatısı.

## Neler var?
- 14 uzman rol: CEO, proje yönetimi, teknoloji mimarisi, yazılım, network/altyapı, araştırma, pazarlama, içerik, ürün/iş, veri, hafıza, QA, güvenlik ve CFO/finans operasyonları.
- SQLite görev, ajan ataması, analiz çıktısı ve denetim kaydı.
- Yerel bilgi hafızası: `remember` / `recall`.
- Şeffaf anahtar-kelime yönlendirmesi ve isteğe bağlı yerel Ollama modeli.
- İsteğe bağlı, izin listeli Telegram görev alımı.

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
- [14 ajan işletim modeli](docs/AGENTS.md)
- [Mimari](docs/ARCHITECTURE.md)
- [Güvenlik](docs/SECURITY.md)
- [Yol haritası](docs/ROADMAP.md)
- [Sahip delegasyonu ve otonom çalışma modeli](docs/OWNER_DELEGATION_AND_AUTONOMY.md)
