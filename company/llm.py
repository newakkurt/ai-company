"""Gemini 3.8 Flash provider with bounded retries and secret-safe errors."""
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class GeminiAPIError(RuntimeError):
    """Safe provider error containing an HTTP status, never an API key."""


class GeminiProvider:
    """Google Gemini API provider. The API key is read only from the environment."""

    DEFAULT_MODEL = "gemini-3.8-flash"
    RETRYABLE_STATUS = {429, 500, 502, 503, 504}
    RETRY_DELAYS = (5, 15)

    def __init__(self, api_key=None, model=None, timeout=45):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = model or os.getenv("AI_COMPANY_GEMINI_MODEL", self.DEFAULT_MODEL)
        self.timeout = timeout

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {"maxOutputTokens": 2048},
        }
        body = json.dumps(payload).encode("utf-8")

        for attempt in range(3):
            request = Request(
                endpoint,
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "x-goog-api-key": self.api_key,
                },
                method="POST",
            )
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    data = json.loads(response.read().decode("utf-8"))
                break
            except HTTPError as exc:
                status = int(exc.code)
                if status in self.RETRYABLE_STATUS and attempt < 2:
                    retry_after = exc.headers.get("Retry-After", "")
                    try:
                        delay = min(max(int(retry_after), 1), 30)
                    except (TypeError, ValueError):
                        delay = self.RETRY_DELAYS[attempt]
                    time.sleep(delay)
                    continue
                raise GeminiAPIError(
                    f"Gemini API returned HTTP {status}; check key access, model, and quota."
                ) from exc
            except (URLError, TimeoutError) as exc:
                if attempt < 2:
                    time.sleep(self.RETRY_DELAYS[attempt])
                    continue
                raise GeminiAPIError(
                    f"Gemini API network request failed ({type(exc).__name__})."
                ) from exc
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise GeminiAPIError("Gemini API returned an invalid JSON response.") from exc
        else:
            raise GeminiAPIError("Gemini API request attempts were exhausted.")

        candidates = data.get("candidates") or []
        parts = (candidates[0].get("content") or {}).get("parts") or [] if candidates else []
        content = "\n".join(part.get("text", "") for part in parts).strip()
        if not content:
            raise GeminiAPIError("Gemini API returned an empty response.")
        return content


def get_provider():
    """Use Gemini 3.8 Flash exclusively; never silently fall back to another model."""
    return GeminiProvider()
