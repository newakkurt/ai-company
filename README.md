# New Akkurt AI Company

Bağımsız, modüler ve insan-onaylı AI şirketi orkestrasyon çatısı.

## Hedef
- Görevleri merkezi orkestratörden ekiplere dağıtmak.
- Her iş için kanıt, çıktı, test ve karar kaydı üretmek.
- Mevcut projeleri değiştirmeden adapter arayüzleriyle yönetmek.
- Güvenli, yerel ve düşük maliyetli çalışmak.

## Ücretsiz ilk sürüm
Python + SQLite + Markdown. Telegram görev alımı isteğe bağlıdır; ücretli API veya bulut sunucu gerekmez. Telegram için ayrı bir bot ve internet bağlantısı gerekir.

## Güvenlik
- Varsayılan mod dry-run'dır.
- Yalnızca TELEGRAM_ALLOWED_CHAT_IDS listesindeki sohbetler görev oluşturabilir.
- Telegram botu yalnızca görev kaydeder; görevleri çalıştırmaz.
- Yayın, deploy, harcama, veri silme ve gerçek cihaz değişikliği insan onayı ister.
- Gizli anahtarlar repoya veya loglara yazılmaz.

## Kurulum
Python 3.10+, Git. Ubuntu veya WSL önerilir.

```bash
git clone https://github.com/newakkurt/ai-company.git
cd ai-company
git checkout feature/sqlite-task-approval
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m company.cli doctor
python -m unittest discover -s tests -v
```

## Yerel görev komutları
```bash
python -m company.cli task "NetCmd için yapılacak işleri analiz et"
python -m company.cli list
python -m company.cli approve TASK_ID --note "İnceledim"
```
Onay komutu yalnızca onay kaydı oluşturur; görevi çalıştırmaz.

## Telegram görev alımı
1. BotFather üzerinden ayrı bir AI Company botu oluştur.
2. Token'ı yerel .env dosyasına koy; GitHub'a veya sohbete gönderme.
3. Numeric chat ID'ni öğren ve allowlist'e ekle.
4. TELEGRAM_BOT_TOKEN ve TELEGRAM_ALLOWED_CHAT_IDS değişkenlerini ayarla.
5. Terminalde `set -a; source .env; set +a` komutuyla değişkenleri yükle.
6. `python -m company.cli telegram-poll` komutunu çalıştır.
7. Telegram'da `/task Görev açıklaması` gönder.

Örnek .env (değerleri kendinle değiştir):
```dotenv
TELEGRAM_BOT_TOKEN=123456:replace-with-your-secret
TELEGRAM_ALLOWED_CHAT_IDS=123456789
```
Bot polling çalışırken makine ve internet bağlantısı açık kalmalıdır.

## Ekipler
CEO / Orchestrator, teknoloji, yazılım, araştırma, pazarlama, hafıza ve QA-güvenlik. Mevcut projeler kendi depolarında kalır; kaynak kodları buraya kopyalanmaz.
