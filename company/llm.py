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
                raw_error = exc.read(8192)
                try:
                    error_payload = json.loads(raw_error.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    error_payload = {}
                error_data = error_payload.get("error") or {}
                safe_message = str(error_data.get("message") or "")[:120]
                quota_ids = []
                for detail in error_data.get("details") or []:
                    quota_failure = detail.get("quotaFailure") or {}
                    for violation in quota_failure.get("violations") or []:
                        quota_id = violation.get("quotaId") or violation.get("quotaMetric")
                        if quota_id and quota_id not in quota_ids:
                            quota_ids.append(str(quota_id)[:100])
                retry_after = (exc.headers or {}).get("Retry-After", "")

                # A 429 may be a per-minute or per-day quota. Do not burn more
                # requests with blind retries; retry only when Google gives a hint.
                if status == 429 and retry_after and attempt < 2:
                    try:
                        delay = min(max(int(retry_after), 1), 900)
                    except (TypeError, ValueError):
                        delay = 60
                    time.sleep(delay)
                    continue
                if status in {500, 502, 503, 504} and attempt < 2:
                    time.sleep(self.RETRY_DELAYS[attempt])
                    continue

                summary = f"Gemini API returned HTTP {status}"
                if quota_ids:
                    summary += "; quota=" + ",".join(quota_ids)
                if safe_message:
                    summary += "; " + safe_message
                if status == 429:
                    summary += "; check Google AI Studio Usage and Rate Limits"
                else:
                    summary += "; check key access, model, and quota"
                raise GeminiAPIError(summary) from exc
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
