"""Gemini Flash-Lite provider with bounded retries and secret-safe errors."""
import json
import os
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class GeminiAPIError(RuntimeError):
    """Safe provider error containing an HTTP status, never an API key."""


class GeminiProvider:
    """Google Gemini API provider. The API key is read only from the environment."""

    DEFAULT_MODEL = "gemini-3.5-flash-lite"
    RETRYABLE_STATUS = {429, 500, 502, 503, 504}
    RETRY_DELAYS = (5, 15)
    supports_search = True

    def __init__(self, api_key=None, model=None, timeout=45):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = model or os.getenv("AI_COMPANY_GEMINI_MODEL", self.DEFAULT_MODEL)
        self.timeout = timeout

    @staticmethod
    def _format_sources(candidate: dict) -> str:
        """Render Google Search grounding sources with the access date (constitution: cite sources)."""
        chunks = (candidate.get("groundingMetadata") or {}).get("groundingChunks") or []
        seen, lines = set(), []
        for chunk in chunks:
            web = chunk.get("web") or {}
            uri = str(web.get("uri") or "").strip()
            if not uri or uri in seen:
                continue
            seen.add(uri)
            title = " ".join(str(web.get("title") or uri).split())[:100]
            lines.append(f"- {title}: {uri}")
            if len(lines) >= 8:
                break
        if not lines:
            return ""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return f"\n\nKaynaklar (Google Search grounding, erişim {today}):\n" + "\n".join(lines)

    def generate(self, system_prompt: str, user_prompt: str, use_search: bool = False) -> str:
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
        if use_search:
            payload["tools"] = [{"google_search": {}}]
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
                safe_message = " ".join(str(error_data.get("message") or "").split())[:180]
                safe_description = " ".join(
                    str(error_data.get("description") or error_payload.get("description") or "").split()
                )[:180]
                provider_status = str(error_data.get("status") or "")[:40]
                detail_types = []
                quota_ids = []
                for detail in error_data.get("details") or []:
                    detail_type = str(detail.get("@type") or "").rsplit(".", 1)[-1]
                    if detail_type and detail_type not in detail_types:
                        detail_types.append(detail_type[:40])
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
                if provider_status:
                    summary += "; provider_status=" + provider_status
                if quota_ids:
                    summary += "; quota=" + ",".join(quota_ids)
                if detail_types:
                    summary += "; details=" + ",".join(detail_types)
                if safe_description:
                    summary += "; description=" + safe_description
                elif safe_message:
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
        if use_search and candidates:
            content += self._format_sources(candidates[0])
        return content


class GroqAPIError(RuntimeError):
    """Safe Groq provider error that never contains an API key."""


class GroqProvider:
    """OpenAI-compatible Groq provider, enabled only when GROQ_API_KEY is configured."""

    DEFAULT_MODEL = "llama-3.1-8b-instant"
    ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, api_key=None, model=None, timeout=45):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        self.model = model or os.getenv("GROQ_MODEL", self.DEFAULT_MODEL)
        self.timeout = timeout

    supports_search = False

    def generate(self, system_prompt: str, user_prompt: str, use_search: bool = False) -> str:
        # use_search is accepted for interface parity; Groq has no grounding tool.
        if not self.api_key:
            raise RuntimeError("GROQ_API_KEY is not configured")
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": 2048,
            "temperature": 0.2,
        }
        request = Request(
            self.ENDPOINT,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": "Bearer " + self.api_key,
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise GroqAPIError(f"Groq API returned HTTP {int(exc.code)}") from exc
        except (URLError, TimeoutError) as exc:
            raise GroqAPIError(
                f"Groq API network request failed ({type(exc).__name__})."
            ) from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GroqAPIError("Groq API returned an invalid JSON response.") from exc

        choices = data.get("choices") or []
        message = (choices[0].get("message") or {}) if choices else {}
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise GroqAPIError("Groq API returned an empty response.")
        return content.strip()


class FallbackProvider:
    """Use Groq only when Gemini is temporarily unavailable or quota-limited."""

    supports_search = True

    def __init__(self, primary, fallback):
        self.primary = primary
        self.fallback = fallback

    def generate(self, system_prompt: str, user_prompt: str, use_search: bool = False) -> str:
        try:
            if use_search:
                return self.primary.generate(system_prompt, user_prompt, use_search=True)
            return self.primary.generate(system_prompt, user_prompt)
        except GeminiAPIError as exc:
            message = str(exc)
            retryable = any(
                marker in message
                for marker in ("HTTP 429", "HTTP 500", "HTTP 502", "HTTP 503", "HTTP 504")
            )
            if not retryable:
                raise
            print(
                "agent_worker: Gemini unavailable; using configured Groq fallback",
                flush=True,
            )
            return self.fallback.generate(system_prompt, user_prompt)


def get_provider():
    """Prefer Gemini; use Groq as a quota-safe fallback when its key is configured."""
    gemini = GeminiProvider() if os.getenv("GEMINI_API_KEY") else None
    groq = GroqProvider() if os.getenv("GROQ_API_KEY") else None
    if gemini and groq:
        return FallbackProvider(gemini, groq)
    if gemini:
        return gemini
    if groq:
        return groq
    return GeminiProvider()
