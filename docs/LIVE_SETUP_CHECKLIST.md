# Canlı Kurulum Kontrol Listesi ("sadece bankaya bak" öncesi)

Bu liste yalnızca **senin** yapabileceğin adımları içerir (hesap, secret, hukuki kimlik). Hiçbir değeri sohbete,
GitHub'a veya koda yazma; yalnızca Render → ai-company → Environment ve GitHub Actions Secrets.
Her adımın sonunda "Doğrula" satırı var; geçmeden sonrakine geçme.
Durum: kanıtlanmış satış **0**. "Gelir üretiyor" ancak banka/BMC bakiyesinde para görününce doğrudur.

## 1. Yapay zekâ kotası (blokaj: görevler dead-letter'a düşüyor)
- [ ] Groq hesabından API key al → Render: `GROQ_API_KEY` (model: `GROQ_MODEL=openai/gpt-oss-20b`).
- [ ] Gemini kotası dolduysa 24 saat bekle; Groq yedek olarak devreye girer.
- Doğrula: `GET /readyz` provider hazır görünür; yeni bir `/task` görevi `completed` olur.

## 2. Telegram (onay ve bildirim kanalı)
- [ ] `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_CHAT_IDS`, `TELEGRAM_OWNER_CHAT_ID` tanımlı.
- [ ] Bot dinleme için tek tüketici: `AI_COMPANY_EMBEDDED_TELEGRAM=true` **ya da** harici `telegram-poll` (ikisi birden değil).
- Doğrula: bota `/approvals` yaz → "Bekleyen onay yok." cevabı gelir.

## 3. Buy Me a Coffee (ödeme)
Ayrıntı: `docs/netcmd-pro-checkout-setup.md`.
- [ ] BMC'de ürün/Shop item oluştur; fiyat ve checkout URL'sini kopyala.
- [ ] Integrations → Webhook: `https://ai-company-ferd.onrender.com/webhooks/buymeacoffee`
      olayları: `membership.started/updated/cancelled/paused` (+ Shop satışı için ilgili olaylar).
- [ ] Render: `BMC_WEBHOOK_SECRET`, `BMC_PRO_MEMBERSHIP_LEVEL_ID`, `BMC_PRO_PRICE_USD`, `BMC_PRO_CHECKOUT_URL`.
- [ ] Shop ürünleri için `BMC_EXTRA_PRODUCT_MAP` (ör. `{"EXTRA_ID":{"product_id":"prd-...","price_usd":"30.00","product_code":"...","product_name":"..."}}`).
- Doğrula: `GET /api/payments/status` (API key ile) → `webhook_secret_configured: true`, `ready_for_live_membership: true`.
  BMC panelinden **test olayı** gönder; endpoint 200 döner, müşteri aktive olmaz (beklenen).

## 4. Teslimat e-postası (SMTP)
- [ ] Ayrı destek posta kutusu aç; `MAIL_SMTP_HOST`, `MAIL_SMTP_PORT=465`, `MAIL_USER`, `MAIL_PASSWORD`, `MAIL_FROM`.
- [ ] Gelen kutusu için `MAIL_IMAP_HOST`, `MAIL_IMAP_PORT=993`.
- [ ] `AI_COMPANY_MAIL_MODE=draft` olarak başla (otomatik yanıt YOK). SPF/DKIM/DMARC kayıtlarını alan adında doğrula.
- Doğrula: kendi adresine bir test teslimat e-postası gönder; spam'e düşmediğini kontrol et.
- `auto_reply` moduna ancak taslak yanıtları 1–2 hafta gözle kontrol ettikten sonra geç.

## 5. Hukuki ve kimlik sayfaları (yayından önce zorunlu)
- [ ] Satıcı kimliği/iletişim, gizlilik politikası (KVKK aydınlatma), mesafeli satış/iade/iptal koşulları, fatura/vergi notu.
- [ ] Siteye bağla ve checkout'tan önce görünür yap.
- Not: dijital içerikte cayma hakkı istisnası ve fatura yükümlülüğü için muhasebeci/avukata danış (ben hukuki tavsiye vermem).

## 6. Uçtan uca gerçek test (para gelmeden "canlı" deme)
- [ ] Ürün fabrikası bir ZIP üretir → Telegram'a "🔐 Onay bekliyor" gelir.
- [ ] Üretilen ürünü **izole ortamda** aç/çalıştır (QA'da çalışma testi `not_run`). Sorun yoksa ✅.
- [ ] Kendi kartınla en düşük fiyatlı ürünü satın al → webhook → teslimat e-postası → "✅ Satış tamamlandı" bildirimi.
- [ ] BMC bakiyesi / banka hareketinde parayı gör (satış webhook'u banka girişi kanıtı değildir).
- [ ] İade sürecini bir kez dene (iade kararı her zaman insan onayındadır).

## 7. Günlük rutin (hedef: günde ~5 dakika)
1. Telegram: bekleyen ✅/❌ onaylar (`/approvals`), her onayda kapsam ve QA satırını oku.
2. Banka/BMC: IBAN hareketi ve bakiye.
3. `python -m company.cli review list`: insan kuyruğundaki istisnalar.

## Bilerek otomatik OLMAYANLAR
- Soğuk e-posta/toplu mesaj ile müşteri avı (KVKK/ETK riski, hesap banı riski): taslak üretilir, gönderim onaylıdır.
- Doğrulanmamış ürünün yayını, iade/ödeme kararları, canlı ağ cihazı değişikliği.
