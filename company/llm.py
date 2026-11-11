"""Gemini 3.8 Flash provider for hosted AI Company agents."""
import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class GeminiProvider:
    """Google Gemini API provider. The API key is read only from the environment."""

    DEFAULT_MODEL = "gemini-3.8-flash"

    def __init__(self, api_key=None, model=None, timeout=120):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = model or os.getenv("AI_COMPANY_GEMINI_MODEL", self.DEFAULT_MODEL)
        self.timeout = timeout

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?{urlencode({'key': self.api_key})}"
        )
        # Gemini 3.8 does not accept legacy temperature/top_p/top_k sampling settings.
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {"maxOutputTokens": 2048},
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
            # Keep secrets out of logs while preserving the provider's safe error text.
            reason = getattr(exc, "reason", None)
            raise RuntimeError(
                f"Gemini 3.8 request failed ({type(exc).__name__}). "
                "Check GEMINI_API_KEY, model access, quota, and network."
            ) from exc
        candidates = data.get("candidates") or []
        parts = (candidates[0].get("content") or {}).get("parts") or [] if candidates else []
        content = "\n".join(part.get("text", "") for part in parts).strip()
        if not content:
            raise RuntimeError("Gemini 3.8 returned an empty response")
        return content


def get_provider():
    """Use Gemini 3.8 Flash exclusively; never silently fall back to an unavailable local model."""
    return GeminiProvider()
