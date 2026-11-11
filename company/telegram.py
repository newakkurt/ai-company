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

    def handle_update(self, update):
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
            self.send_message(chat_id, "AI Company görev botu hazır.\nYeni görev: /task Görev açıklaması\nBu bot yalnızca görev kaydeder; görevleri çalıştırmaz.")
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

    def poll_forever(self):
        offset = None
        while True:
            payload = {"timeout": 25, "allowed_updates": json.dumps(["message"])}
            if offset is not None:
                payload["offset"] = offset
            updates = self._api("getUpdates", payload, timeout=35)
            for update in updates:
                update_id = update.get("update_id")
                if isinstance(update_id, int):
                    offset = update_id + 1
                try:
                    self.handle_update(update)
                except Exception:
                    # Do not print tokens, chat content, or personal data to logs.
                    continue
            time.sleep(0.2)
