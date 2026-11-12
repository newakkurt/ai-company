# Otonom Çalışma Kurulumu

Bu sürümle şirket kendi işini üretir, sonuçları ve satışları sana Telegram'dan bildirir, gelen maillere cevap hazırlar/verir. Hepsi **analiz + taslak** sınırında kalır; para, yayın, deploy, cihaz erişimi yoktur.

## Ne otomatik çalışır?

| Parça | Ne yapar | Açma şartı |
|---|---|---|
| Scheduler (`company/scheduler.py`) | Her gün 06:00'dan sonra (TR saati) 4 görev, haftada 1 değerlendirme görevi üretir: TR potansiyel müşteri araştırması, yurtdışı potansiyel müşteri araştırması, ürün fırsatı taraması, içerik taslağı, haftalık gözden geçirme. Görev kimliği gün/hafta bazlıdır, tekrar üretmez. | Varsayılan açık. Kapatmak: `AI_COMPANY_AUTO_TASKS=false` |
| Web araması | `research_intelligence`, `marketing_growth`, `product_business` Gemini'nin Google Search grounding özelliğiyle gerçek kaynak bulur; çıktıya kaynak URL + erişim tarihi eklenir. | `GEMINI_API_KEY` |
| Otomatik retry | Başarısız görev 30 dk sonra en fazla 2 kez yeniden kuyruğa girer, kayıtlı ajan çıktıları tekrar üretilmez. | Otomatik |
| Satış bildirimi | İmzalı BMC webhook'u doğrulanınca Telegram'a "Satış tamamlandı, bankanızı kontrol edin" gider. Beklenmeyen plan/fiyat/olay türü de "manuel kontrol" olarak bildirilir. İptaller de. | `BMC_*` + Telegram |
| Günlük rapor | `auto-*` görevleri bitince CEO özeti Telegram'a gelir. Hata olursa da haber verir. | Telegram |
| Mail | IMAP'ten okunmamış mailleri alır, taslak yazar. | Aşağıya bak |
| Telegram intake | Web servisinin içinde çalışır; ağ kesintisinde kendini toparlar. | `AI_COMPANY_EMBEDDED_TELEGRAM=true` |

## Render ortam değişkenleri

Mevcutlara ek olarak:

```text
TELEGRAM_BOT_TOKEN=...            # BotFather
TELEGRAM_ALLOWED_CHAT_IDS=...     # python -m company.cli telegram-id ile bul
AI_COMPANY_EMBEDDED_TELEGRAM=true
AI_COMPANY_AUTO_TASKS=true
```

Mail için (ayrı bir destek posta kutusu aç; ana kutunu bağlama):

```text
AI_COMPANY_EMBEDDED_MAIL=true
MAIL_IMAP_HOST=imap.gmail.com
MAIL_SMTP_HOST=smtp.gmail.com
MAIL_USER=destek@...
MAIL_PASSWORD=<uygulama şifresi>
MAIL_KNOWLEDGE=Ürün: NetCmd ... (ajanın söyleyebileceği doğrulanmış bilgiler)
AI_COMPANY_MAIL_MODE=draft        # önce draft ile birkaç gün izle
```

## Mail güvenlik modeli

- Varsayılan mod `draft`: hiçbir şey gönderilmez, taslak Telegram'a düşer. Güvendikten sonra `AI_COMPANY_MAIL_MODE=auto_reply`.
- Sadece **sana gelen** maile cevap verilir. Soğuk e-posta / toplu gönderim yoktur.
- Para iadesi, itiraz, fatura, hukuk/KVKK/GDPR, sözleşme, güvenlik açığı bildirimi gibi konular **asla otomatik cevaplanmaz**, sana Telegram'dan iletilir.
- `no-reply`, bülten, `Auto-Submitted`, `Precedence: bulk` gibi otomatik göndericilere cevap verilmez; kendi cevabımız `Auto-Submitted: auto-replied` taşır, mail döngüsü oluşmaz.
- `MAIL_KNOWLEDGE` dışında bilgi/fiyat/söz verilmez; bilinmeyen için "sahibimiz dönüş yapacak" denir.
- Taslakta izinli listesi dışında link varsa gönderilmez, sana iletilir.
- Günlük toplam (20) ve gönderen başına (2) üst sınır. Sayaç süreç yeniden başlayınca sıfırlanır.
- Cevap her zaman "otomatik yapay zekâ asistanı" imzası taşır.

## Doğrulama

`GET /readyz` artık `services` bloğunu da döner (scheduler, notifier, mail, telegram). Canlıda bir test satışı veya BMC test olayı dışında satış bildirimini uçtan uca doğrulayamazsın; BMC'nin "test event"leri (`live_mode=false`) bilerek yok sayılır.

## Bilinen sınırlar (dürüst durum)

- Render Free uyur/yeniden başlar; "7/24" garantisi yoktur (bkz. `continuous-agent-worker-setup.md`).
- Potansiyel müşteri listesi şu an ajan çıktısı metnidir; yapılandırılmış CRM/dedupe tablosu yoktur.
- Soğuk e-posta gönderimi, sosyal medya yayını, kod yazıp PR açma, ürün inşası henüz **yoktur**; ajanlar bunlar için plan/taslak üretir.
- Gelir raporu için ödeme kayıtlarını listeleyen bir araç yoktur; CFO ajanı veri verilmedikçe rakam üretmez.
- Webhook bildirimi "satış gerçekleşti" der; paranın bankaya geçtiğini doğrulamak sende kalır.
