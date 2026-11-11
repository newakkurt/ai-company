# New Akkurt AI Company

Bağımsız, modüler ve insan-onaylı AI şirketi orkestrasyon çatısı.

## Hedef
- Görevleri merkezi orkestratörden ekip ajanlarına dağıtmak.
- Her iş için kanıt, çıktı, test ve karar kaydı üretmek.
- Mevcut projeleri değiştirmeden adapter arayüzleriyle yönetmek.
- İlk sürümde güvenli, yerel ve düşük maliyetli çalışmak.

## Ücretsiz ilk sürüm
Python + SQLite + Markdown. İlk çalıştırma için ücretli API, Apify, fal.ai veya bulut sunucu gerekmez. Model ve Telegram bağlantıları sonraki aşamalarda isteğe bağlı eklenecek.

## Güvenlik ilkeleri
1. Varsayılan mod `dry-run` / planlama modudur.
2. Yayın, deploy, harcama, veri silme ve gerçek cihaz değişikliği insan onayı ister.
3. Gizli anahtarlar repoya veya loglara yazılmaz.
4. Ajan çıktıları doğrulanması gereken öneridir.
5. Onay komutu yalnızca onayı kaydeder; kendiliğinden işlem başlatmaz.

## Gereksinimler
- Python 3.10+
- Git
- Ubuntu veya WSL önerilir
- İlk test için API anahtarı gerekmez

## Hızlı başlangıç
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
python -m company.cli doctor
python -m unittest discover -s tests -v
python -m company.cli task "NetCmd için yapılacak işleri analiz et"
python -m company.cli list
```

Bir görevin onayını kaydetmek için:
```bash
python -m company.cli approve TASK_ID --note "İnceledim"
```
Bu komut görevi çalıştırmaz; yalnızca insan onayı kaydı oluşturur.

## Ekipler
CEO / Orchestrator, teknoloji, yazılım, araştırma, pazarlama, hafıza ve QA-güvenlik. Detaylar için `docs/ARCHITECTURE.md`.

Mevcut projelerin kaynak kodları bu depoya kopyalanmaz. Her proje kendi deposunda kalır.
