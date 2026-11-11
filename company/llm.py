"""Optional Gemini cloud or Ollama local model providers."""
import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class GeminiProvider:
    """Google Gemini API provider. The API key is read only from the environment."""

    def __init__(self, api_key=None, model=None, timeout=120):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = model or os.getenv("AI_COMPANY_GEMINI_MODEL", "gemini-2.5-flash")
        self.timeout = timeout

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?{urlencode({'key': self.api_key})}"
        )
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2048},
        }
        request = Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise RuntimeError(
                "Gemini request failed. Check the API key, model availability, quota, and network."
            ) from exc
        candidates = data.get("candidates") or []
        parts = (candidates[0].get("content") or {}).get("parts") or [] if candidates else []
        content = "\n".join(part.get("text", "") for part in parts).strip()
        if not content:
            raise RuntimeError("Gemini returned an empty response")
        return content


class OllamaProvider:
    """Optional local Ollama provider for development and local use."""

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


def get_provider():
    """Prefer cloud Gemini on hosted deployments; otherwise use local Ollama."""
    if os.getenv("GEMINI_API_KEY"):
        return GeminiProvider()
    return OllamaProvider()
