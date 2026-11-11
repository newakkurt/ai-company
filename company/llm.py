"""Optional local Ollama provider. No cloud API or external writes."""
import json
import os
from urllib.request import Request, urlopen


class OllamaProvider:
    def __init__(self, base_url=None, model=None, timeout=180):
        self.base_url = (base_url or os.getenv("AI_COMPANY_OLLAMA_URL", "http://127.0.0.1:11434")).rstrip("/")
        self.model = model or os.getenv("AI_COMPANY_OLLAMA_MODEL", "qwen2.5:7b")
        self.timeout = timeout

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self.model, "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {"temperature": 0.2},
        }
        request = Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise RuntimeError(
                "Local Ollama request failed. Check that Ollama is running and the configured model is installed."
            ) from exc
        content = (data.get("message") or {}).get("content", "").strip()
        if not content:
            raise RuntimeError("Local model returned an empty response")
        return content
