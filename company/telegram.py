"""Minimal Telegram task intake. Accepts tasks only; never executes them."""
import json
import os
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .store import TaskStore

class TelegramIntake:
    def __init__(self, token=None, allowed_chat_ids=None, store=None):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        raw_ids = allowed_chat_ids
        if raw_ids is None:
            raw_ids = os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "")
        if isinstance(raw_ids, str):
            self.allowed_chat_ids = {part.strip() for part in raw_ids.split(",") if part.strip()}
        else:
            self.allowed_chat_ids = {str(value).strip() for value in (raw_ids or [])}
        self.store = store or TaskStore()
        if not self.token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        if not self.allowed_chat_ids:
            raise ValueError("TELEGRAM_ALLOWED_CHAT_IDS must contain at least one chat ID")

    def _api(self, method, payload=None, timeout=35):
        url = f"https://api.telegram.org/bot{self.token}/{method}"
        body = urlencode(payload or {}).encode()
        request = Request(url, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
        if not result.get("ok"):
            raise RuntimeError(f"Telegram API returned an unsuccessful response for {method}")
        return result["result"]

    def send_message(self, chat_id, text):
        return self._api("sendMessage", {"chat_id": str(chat_id), "text": text})

    def answer_callback(self, callback_id, text):
        try:
            self._api("answerCallbackQuery", {"callback_query_id": callback_id, "text": text[:180]})
        except Exception as exc:  # noqa: BLE001 - never log URL (contains token)
            print(f"telegram: answerCallback failed; error_type={type(exc).__name__}", flush=True)

    def handle_callback(self, callback):
        """One-tap approval. Records the decision only; the protected action still has to
        consume the approval (exact action + scope, single use) when it actually runs."""
        data = str(callback.get("data") or "")
        sender_id = str((callback.get("from") or {}).get("id", ""))
        chat_id = str(((callback.get("message") or {}).get("chat") or {}).get("id", ""))
        if sender_id not in self.allowed_chat_ids or chat_id not in self.allowed_chat_ids:
            return False
        prefix, _, rest = data.partition(":")
        decision_code, _, approval_id = rest.partition(":")
        if prefix != "apv" or decision_code not in {"ok", "no"} or not approval_id.startswith("approval-"):
            self.answer_callback(callback.get("id"), "Geçersiz işlem.")
            return True
        decision = "approved" if decision_code == "ok" else "rejected"
        try:
            self.store.decide_approval_request(approval_id, decision, f"telegram:{sender_id}")
            result = "✅ Onaylandı (tek kullanımlık)" if decision == "approved" else "❌ Reddedildi"
        except KeyError:
            result = "Talep bulunamadı."
        except ValueError:
            result = "Talep süresi dolmuş veya daha önce karara bağlanmış."
        self.answer_callback(callback.get("id"), result)
        try:
            self.send_message(chat_id, f"{result}\nTalep: {approval_id}")
        except Exception as exc:  # noqa: BLE001
            print(f"telegram: confirm failed; error_type={type(exc).__name__}", flush=True)
        return True

    def handle_update(self, update):
        if update.get("callback_query"):
            return self.handle_callback(update["callback_query"])
        message = update.get("message") or update.get("edited_message")
        if not message:
            return False
        chat = message.get("chat") or {}
        chat_id = str(chat.get("id", ""))
        if chat_id not in self.allowed_chat_ids:
            return False
        text = (message.get("text") or "").strip()
        if not text:
            return False

        command, _, argument = text.partition(" ")
        command = command.split("@", 1)[0].lower()
        if command in ("/start", "/help"):
            self.send_message(
                chat_id,
                "AI Company yönetim botu hazır.\\n"
                "/status - yapılandırma özeti\\n"
                "/agents - uzman ajan listesi\\n"
                "/tasks - son görevler\\n"
                "/report - görev özeti\\n"
                "/task Açıklama - yeni dry-run görev kaydı\\n"
                "/approvals - bekleyen onaylar\\n"
                "Not: Bu bot doğrudan cihaz veya dış sistem işlemi çalıştırmaz."
            )
            return True
        if command == "/status":
            required = ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_DB_GATE_KEY")
            db_ready = all(os.getenv(key, "").strip() for key in required)
            ai_ready = bool(os.getenv("GEMINI_API_KEY", "").strip() or os.getenv("GROQ_API_KEY", "").strip())
            worker_enabled = os.getenv("AI_COMPANY_EMBEDDED_WORKER", "").strip().lower() == "true"
            telegram_enabled = os.getenv("AI_COMPANY_EMBEDDED_TELEGRAM", "").strip().lower() == "true"
            lines = [
                "AI Company yapılandırma durumu",
                f"AI anahtarı: {'var' if ai_ready else 'eksik'}",
                f"Supabase ayarları: {'tam' if db_ready else 'eksik (SQLite/fallback olabilir)'}",
                f"Render gömülü worker: {'açık' if worker_enabled else 'kapalı'}",
                f"Telegram polling: {'açık' if telegram_enabled else 'kapalı'}",
                "Çalışma modu: analiz / dry-run",
                "Canlı servis sağlığı bu komutla doğrulanmaz; yalnızca ayarlar gösterilir."
            ]
            self.send_message(chat_id, "\\n".join(lines))
            return True
        if command == "/agents":
            from .agents import agent_summary
            agents = agent_summary()
            lines = [f"Uzman ajanlar ({len(agents)})"]
            lines.extend(f"- {item['name']} [{item['id']}]" for item in agents)
            self.send_message(chat_id, "\\n".join(lines)[:3800])
            return True
        if command == "/tasks":
            tasks = self.store.list_tasks(limit=5)
            if not tasks:
                self.send_message(chat_id, "Henüz görev kaydı yok.")
                return True
            lines = ["Son görevler"]
            for item in tasks:
                description = " ".join(str(item.get("description") or "").split())
                if len(description) > 110:
                    description = description[:107] + "..."
                lines.append(f"- {item.get('status', 'unknown')}: {description or item.get('task_id', 'Görev')}")
            self.send_message(chat_id, "\\n".join(lines)[:3800])
            return True
        if command == "/report":
            tasks = self.store.list_tasks(limit=100)
            counts = {}
            for item in tasks:
                status = str(item.get("status") or "unknown")
                counts[status] = counts.get(status, 0) + 1
            lines = [f"Görev özeti (son {len(tasks)} kayıt)"]
            lines.extend(f"- {status}: {count}" for status, count in sorted(counts.items()))
            if not counts:
                lines.append("- Henüz görev yok")
            lines.append("Not: Bu rapor yalnızca kayıtlı görevleri sayar; gelir veya satış doğrulaması değildir.")
            self.send_message(chat_id, "\\n".join(lines)[:3800])
            return True
        if command == "/approvals":
            from .notifier import approval_keyboard, format_approval_message
            pending = self.store.list_approval_requests(status="pending", limit=10)
            if not pending:
                self.send_message(chat_id, "Bekleyen onay yok.")
            for item in pending:
                self._api("sendMessage", {"chat_id": chat_id, "text": format_approval_message(item)[:3800],
                                          "reply_markup": json.dumps(approval_keyboard(item["approval_id"]))})
            return True
        if command == "/task":
            if not argument.strip():
                self.send_message(chat_id, "Kullanım: /task Yapılmasını istediğin işi yaz")
                return True
            task = self.store.create_task(argument.strip())
            self.send_message(chat_id, f"Görev kaydedildi: {task['task_id']}\nDurum: planned (dry_run)\nHerhangi bir işlem çalıştırılmadı.")
            return True
        self.send_message(chat_id, "Komut anlaşılmadı. Yardım için /help yaz.")
        return True

    def pending_chat_ids(self):
        """Read pending updates and return only numeric chat IDs, never message text."""
        updates = self._api(
            "getUpdates",
            {"timeout": 0, "allowed_updates": json.dumps(["message", "callback_query"])},
            timeout=10
        )
        ids = {
            str((update.get("message") or {}).get("chat", {}).get("id"))
            for update in updates
            if (update.get("message") or {}).get("chat", {}).get("id") is not None
        }
        return sorted(ids)

    def _wait(self, stop_event, seconds):
        if stop_event is not None:
            stop_event.wait(seconds)
        else:
            time.sleep(seconds)

    def poll_forever(self, stop_event=None):
        """Long-poll until stop_event is set. Network errors back off instead of killing the loop."""
        offset = None
        backoff = 5
        while stop_event is None or not stop_event.is_set():
            payload = {"timeout": 25, "allowed_updates": json.dumps(["message", "callback_query"])}
            if offset is not None:
                payload["offset"] = offset
            try:
                updates = self._api("getUpdates", payload, timeout=35)
                backoff = 5
            except Exception as exc:  # noqa: BLE001 - exception text may contain the bot token URL
                print(f"telegram: poll failed; error_type={type(exc).__name__}", flush=True)
                self._wait(stop_event, backoff)
                backoff = min(backoff * 2, 60)
                continue
            for update in updates:
                update_id = update.get("update_id")
                if isinstance(update_id, int):
                    offset = update_id + 1
                try:
                    self.handle_update(update)
                except Exception:
                    # Do not print tokens, chat content, or personal data to logs.
                    continue
            self._wait(stop_event, 0.2)
