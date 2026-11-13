# Agent Harness (ANAYASA "Agent Harness Kuralları")

| Prensip | Modül | Zorlama |
|---|---|---|
| 1 Kademeli yönlendirme + gizlilik | `harness/privacy.py`, `harness/routing.py` | `TieredProvider` hassas veriyi buluttan keser; uygun tier yoksa `PrivacyRoutingError` → insan kuyruğu |
| 2 Durum makinesi + izlenebilirlik | `harness/state_machine.py` | `TRANSITIONS` tablosu; `data/traces/<task>.jsonl` hash zinciri; `ai-company trace <id> --verify` |
| 3 Kontrol noktası + HITL | `harness/escalation.py`, `harness/safety.py` | `verify_output`, `check_command`, `run_with_retries` (≤3), `HumanReviewQueue` (SQLite) |
| 4 Bağlam / bellek | `harness/context_gate.py` | `select_context` (tier başına araç/token sınırı), `fits_in_budget` |
| 5 Dar kapsam | `harness/tools.py` | sandbox'lı `read/write/edit/bash`, shell varsayılan KAPALI |

## Varsayılan davranış (geriye uyumlu)
Hosted/Render akışı değişmedi: `get_provider()` Gemini (+Groq yedek) döner. Tiered mod yalnızca
`AI_COMPANY_ROUTING=tiered` veya bir `AI_COMPANY_LOCAL_*_URL` tanımlıysa açılır. Üretimde yerel model
yoksa gizli veri içeren görev buluta gönderilmez, insan kuyruğuna düşer (fail-closed).

## Yerel model kurulumu (Ollama / llama.cpp, OpenAI-uyumlu)
```
AI_COMPANY_ROUTING=tiered
AI_COMPANY_LOCAL_SMALL_URL=http://127.0.0.1:11434/v1
AI_COMPANY_LOCAL_SMALL_MODEL=<2B-4B model etiketi, ör. ollama list çıktısındaki MiniCPM>
AI_COMPANY_LOCAL_LARGE_URL=http://127.0.0.1:11434/v1
AI_COMPANY_LOCAL_LARGE_MODEL=<27B-32B model etiketi, ör. Qwen>
AI_COMPANY_ALLOW_CLOUD=true   # false: hiçbir istek buluta gitmez
AI_COMPANY_MEM_LIMIT_GB=32
```
Endpoint loopback/özel ağ olmalıdır; aksi halde `AI_COMPANY_LOCAL_ALLOW_REMOTE=true` gerekir.
Model etiketlerini kendi makinende `ollama list` ile doğrula; depo sabit model adı varsaymaz.

## CLI
```
python -m company.cli route-check "metin" --kind blueprint   # hangi tier görebilir?
python -m company.cli review list | approve <id> | reject <id>
python -m company.cli trace <task_id> --verify
```

## Sınırlar (dürüst durum)
- Gizlilik taraması desen tabanlıdır (TC checksum, Luhn, IBAN, sır/anahtar, iç IP, anahtar kelime); isim/adres
  gibi serbest metin kişisel verileri yakalamaz. Kritik veri için `AI_COMPANY_ALLOW_CLOUD=false` kullan.
- İnsan kuyruğu yerel SQLite'tır (`data/human_review.db`); Render Free'de dosya sistemi geçicidir, kalıcı
  kuyruk için kalıcı disk veya Supabase tablosu gerekir.
- Yerel model gerçek uçtan uca testi bu ortamda yapılmadı (GPU/Ollama yok); `LocalProvider` HTTP sözleşmesi
  ve yönlendirme mantığı birim testlerle doğrulandı.
- Durum makinesi mevcut `tasks.status` sütununu değiştirmez; geçişler ek iz kaydıdır.
