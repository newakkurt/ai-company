"""Owner notifications over Telegram.

Best-effort by design: a failed notification must never break the worker, the
webhook, or the mailbox loop. Only exception class names are logged, never
messages (Telegram URLs contain the bot token).
"""
from __future__ import annotations

import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen

MAX_LEN = 3800  # Telegram hard limit is 4096 characters.


def owner_chat_id() -> str:
    """Owner chat: TELEGRAM_OWNER_CHAT_ID, else the first allow-listed chat."""
    explicit = os.getenv("TELEGRAM_OWNER_CHAT_ID", "").strip()
    if explicit:
        return explicit
    allowed = [p.strip() for p in os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "").split(",") if p.strip()]
    return allowed[0] if allowed else ""


def _post(token: str, chat_id: str, text: str, reply_markup: dict | None = None) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    fields = {"chat_id": chat_id, "text": text, "disable_web_page_preview": "true"}
    if reply_markup:
        fields["reply_markup"] = json.dumps(reply_markup)
    body = urlencode(fields).encode()
    request = Request(url, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urlopen(request, timeout=15) as response:
        return bool(json.loads(response.read().decode("utf-8")).get("ok"))


def notifier_configured() -> bool:
    return bool(os.getenv("TELEGRAM_BOT_TOKEN", "").strip() and owner_chat_id())


def notify_owner(text: str, sender=None, reply_markup: dict | None = None) -> bool:
    """Send a message to the owner. Returns False instead of raising."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = owner_chat_id()
    text = (text or "").strip()
    if not token or not chat_id or not text:
        return False
    try:
        if reply_markup:
            return bool((sender or _post)(token, chat_id, text[:MAX_LEN], reply_markup))
        return bool((sender or _post)(token, chat_id, text[:MAX_LEN]))
    except Exception as exc:  # noqa: BLE001 - never leak URL/token via exception text
        print(f"notifier: send failed; error_type={type(exc).__name__}", flush=True)
        return False


_SALE_HEADLINES = {
    "membership.started": "✅ Satış tamamlandı",
    "membership.updated": "🔁 Üyelik yenilendi / güncellendi",
}


def format_sale_message(event_type: str, membership: dict) -> str:
    """Sale notice. Deliberately excludes buyer e-mail/name (no PII in chat logs)."""
    headline = _SALE_HEADLINES.get(event_type, "✅ Satış bildirimi")
    product = membership.get("membership_level_name") or "NetCmd PRO"
    amount = membership.get("amount")
    currency = membership.get("currency") or ""
    return (
        f"{headline}\n"
        f"Ürün: {product}\n"
        f"Tutar: {amount} {currency}\n"
        "Kaynak: Buy Me a Coffee (imzalı webhook doğrulandı)\n\n"
        "🏦 Bankanızı / BMC bakiyenizi kontrol edin. "
        "Para hesabınıza geçmeden gelir sayılmaz."
    )


def notify_sale(event_type: str, membership: dict, sender=None) -> bool:
    return notify_owner(format_sale_message(event_type, membership), sender=sender)


def notify_cancellation(subscription_id: str, status: str, sender=None) -> bool:
    return notify_owner(
        f"⚠️ Üyelik {status}: {subscription_id}\nGelir etkisini kontrol edin.", sender=sender
    )


def notify_unexpected_payment(event_type: str, reason: str, data: dict, sender=None) -> bool:
    """A signed live event we did NOT activate: the owner must look at it manually."""
    return notify_owner(
        "🔎 Manuel kontrol gerekiyor: ödeme sağlayıcısından canlı bir olay geldi ama "
        f"otomatik aktivasyon yapılmadı.\nOlay: {event_type}\nNeden: {reason}\n"
        f"Plan ID: {data.get('membership_level_id')} | Tutar: {data.get('amount')} "
        f"{data.get('currency')}\nBankanızı / BMC panelinizi kontrol edin.",
        sender=sender,
    )


def notify_task_result(task: dict, sender=None) -> bool:
    """Digest for autonomous (auto-*) tasks: the CEO synthesis, trimmed."""
    outputs = {o["agent_id"]: o["output_text"] for o in task.get("agent_outputs", [])}
    summary = outputs.get("ceo") or next(iter(outputs.values()), "")
    if not summary:
        return False
    return notify_owner(
        f"📋 Otomatik görev tamamlandı: {task['task_id']}\n\n{summary[:3000]}\n\n"
        "(Ajan çıktısıdır; doğrulanmamış öneri olarak değerlendirin.)",
        sender=sender,
    )


def notify_task_failed(task_id: str, error_type: str, sender=None) -> bool:
    return notify_owner(f"❌ Görev başarısız: {task_id}\nHata türü: {error_type}", sender=sender)


def format_approval_message(approval: dict) -> str:
    """Owner-facing summary of ONE scoped approval. Scope is redacted and trimmed."""
    from .harness.privacy import redact
    scope = redact(json.dumps(approval.get("scope_json") or {}, ensure_ascii=False, sort_keys=True))[0]
    return (
        "🔐 Onay bekliyor\n"
        f"İşlem: {approval.get('action')}\n"
        f"Kapsam: {scope[:900]}\n"
        f"Talep eden: {approval.get('requested_by')}\n"
        f"Geçerlilik: {approval.get('expires_at')}\n\n"
        "Onay yalnızca bu tek işlem ve kapsam için geçerlidir; tek kullanımlıktır."
    )


def approval_keyboard(approval_id: str) -> dict:
    return {"inline_keyboard": [[
        {"text": "✅ Onayla", "callback_data": f"apv:ok:{approval_id}"},
        {"text": "❌ Reddet", "callback_data": f"apv:no:{approval_id}"},
    ]]}


def notify_approval_request(approval: dict, sender=None, extra: str = "") -> bool:
    """Send an approval request with one-tap Approve/Reject buttons (best-effort)."""
    if not approval or not approval.get("approval_id"):
        return False
    text = format_approval_message(approval) + (("\n\n" + extra.strip()) if extra.strip() else "")
    return notify_owner(text, sender=sender,
                        reply_markup=approval_keyboard(approval["approval_id"]))
