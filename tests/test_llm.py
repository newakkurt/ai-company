import json
import io
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from company.llm import (
    FallbackProvider,
    GeminiAPIError,
    GeminiProvider,
    GroqAPIError,
    GroqProvider,
    _get_cloud_provider,
    normalize_api_key,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


class GeminiProviderTests(unittest.TestCase):
    def test_default_model_is_flash_lite_for_high_volume_worker(self):
        self.assertEqual(GeminiProvider.DEFAULT_MODEL, "gemini-3.5-flash-lite")

    def test_groq_default_model_is_current_free_plan_model(self):
        self.assertEqual(GroqProvider.DEFAULT_MODEL, "openai/gpt-oss-20b")

    def test_groq_provider_uses_bearer_header_and_configured_model(self):
        response = FakeResponse(
            b'{"choices":[{"message":{"content":"Groq OK"}}]}'
        )
        with patch("company.llm.urlopen", return_value=response) as request:
            provider = GroqProvider(api_key="groq-test-key")
            self.assertEqual(provider.generate("system", "user"), "Groq OK")

        sent_request = request.call_args.args[0]
        self.assertEqual(sent_request.full_url, GroqProvider.ENDPOINT)
        self.assertEqual(sent_request.get_header("Authorization"), "Bearer groq-test-key")
        self.assertNotIn("groq-test-key", sent_request.full_url)
        self.assertEqual(request.call_args.kwargs["timeout"], 45)


    def test_normalize_api_key_removes_whitespace_and_matching_quotes(self):
        self.assertEqual(normalize_api_key('  "gsk-example-key"  \n'), "gsk-example-key")

    def test_groq_api_key_is_trimmed_before_auth_header(self):
        response = FakeResponse(b'{"choices":[{"message":{"content":"Groq OK"}}]}')
        with patch("company.llm.urlopen", return_value=response) as request:
            provider = GroqProvider(api_key="  groq-test-key\n")
            self.assertEqual(provider.generate("system", "user"), "Groq OK")
        self.assertEqual(request.call_args.args[0].get_header("Authorization"), "Bearer groq-test-key")


    def test_groq_tpm_429_waits_and_retries_once(self):
        rate_limit = HTTPError(
            GroqProvider.ENDPOINT,
            429,
            "Too Many Requests",
            {"Retry-After": "60"},
            io.BytesIO(b'{"error":{"message":"Rate limit reached for tokens per minute"}}'),
        )
        success = FakeResponse(b'{"choices":[{"message":{"content":"Groq OK"}}]}')
        with patch("company.llm.urlopen", side_effect=[rate_limit, success]):
            with patch("company.llm.time.sleep") as sleep:
                provider = GroqProvider(api_key="groq-test-key")
                self.assertEqual(provider.generate("system", "user"), "Groq OK")
        sleep.assert_called_once_with(60)

    def test_groq_tpm_413_waits_and_retries_once(self):
        rate_limit = HTTPError(
            GroqProvider.ENDPOINT,
            413,
            "Request too large",
            {},
            io.BytesIO(b'{"error":{"message":"Requested 10000 tokens, limit 8000 tokens per minute"}}'),
        )
        success = FakeResponse(b'{"choices":[{"message":{"content":"Groq OK"}}]}')
        with patch("company.llm.urlopen", side_effect=[rate_limit, success]) as request:
            with patch("company.llm.time.sleep") as sleep:
                provider = GroqProvider(api_key="groq-test-key")
                self.assertEqual(provider.generate("system", "user"), "Groq OK")
        self.assertEqual(request.call_count, 2)
        sleep.assert_called_once_with(60)

    def test_groq_system_prompt_states_that_no_tools_exist(self):
        response = FakeResponse(b'{"choices":[{"message":{"content":"Groq OK"}}]}')
        with patch("company.llm.urlopen", return_value=response) as request:
            GroqProvider(api_key="groq-test-key").generate("system", "user")
        payload = json.loads(request.call_args.args[0].data.decode("utf-8"))
        self.assertNotIn("tools", payload)
        self.assertIn("No tools", payload["messages"][0]["content"])

    def test_groq_phantom_tool_call_400_is_retried_then_succeeds(self):
        def phantom():
            return HTTPError(
                GroqProvider.ENDPOINT, 400, "Bad Request", {},
                io.BytesIO(b'{"error":{"message":"Tool choice is none, but model called a tool"}}'),
            )
        success = FakeResponse(b'{"choices":[{"message":{"content":"Groq OK"}}]}')
        with patch("company.llm.urlopen", side_effect=[phantom(), phantom(), success]) as request:
            self.assertEqual(GroqProvider(api_key="groq-test-key").generate("s", "u"), "Groq OK")
        self.assertEqual(request.call_count, 3)

    def test_groq_phantom_tool_call_retry_is_bounded(self):
        def phantom():
            return HTTPError(
                GroqProvider.ENDPOINT, 400, "Bad Request", {},
                io.BytesIO(b'{"error":{"message":"Tool choice is none, but model called a tool"}}'),
            )
        with patch("company.llm.urlopen", side_effect=[phantom(), phantom(), phantom(), phantom()]) as request:
            with self.assertRaises(GroqAPIError):
                GroqProvider(api_key="groq-test-key").generate("s", "u")
        self.assertEqual(request.call_count, 3)

    def test_groq_uses_a_small_default_output_budget(self):
        response = FakeResponse(b'{"choices":[{"message":{"content":"Groq OK"}}]}')
        with patch("company.llm.urlopen", return_value=response) as request:
            GroqProvider(api_key="groq-test-key").generate("system", "user")
        payload = json.loads(request.call_args.args[0].data.decode("utf-8"))
        self.assertLessEqual(payload["max_tokens"], 2048)

    def test_groq_http_error_exposes_status_and_safe_provider_message(self):
        response = io.BytesIO(b'{"error":{"message":"Invalid API Key"}}')
        error = HTTPError(
            GroqProvider.ENDPOINT, 401, "Unauthorized", {}, response
        )
        with patch("company.llm.urlopen", side_effect=error):
            with self.assertRaises(GroqAPIError) as raised:
                GroqProvider(api_key="groq-test-secret").generate("system", "user")
        self.assertIn("HTTP 401", str(raised.exception))
        self.assertIn("Invalid API Key", str(raised.exception))
        self.assertNotIn("groq-test-secret", str(raised.exception))


    def test_groq_http_error_redacts_tokens_from_plain_text_body(self):
        response = io.BytesIO(b"Access denied for gsk_abcdefghijklmnop123456")
        error = HTTPError(GroqProvider.ENDPOINT, 403, "Forbidden", {}, response)
        with patch("company.llm.urlopen", side_effect=error):
            with self.assertRaises(GroqAPIError) as raised:
                GroqProvider(api_key="groq-test-secret").generate("system", "user")
        self.assertIn("HTTP 403", str(raised.exception))
        self.assertIn("Access denied", str(raised.exception))
        self.assertNotIn("gsk_abcdefghijklmnop123456", str(raised.exception))

    def test_fallback_uses_groq_when_gemini_quota_is_exhausted(self):
        class Primary:
            def generate(self, *_args):
                raise GeminiAPIError("Gemini API returned HTTP 429; quota exhausted")

        class Fallback:
            def generate(self, *_args):
                return "Fallback output"

        provider = FallbackProvider(Primary(), Fallback())
        self.assertEqual(provider.generate("system", "user"), "Fallback output")

    def test_fallback_does_not_hide_invalid_gemini_key(self):
        class Primary:
            def generate(self, *_args):
                raise GeminiAPIError("Gemini API returned HTTP 401")

        class Fallback:
            def generate(self, *_args):
                raise AssertionError("Fallback must not run for invalid credentials")

        provider = FallbackProvider(Primary(), Fallback())
        with self.assertRaises(GeminiAPIError):
            provider.generate("system", "user")

    def test_api_key_is_sent_in_header_not_url(self):
        response = FakeResponse(
            b'{"candidates":[{"content":{"parts":[{"text":"OK"}]}}]}'
        )
        with patch("company.llm.urlopen", return_value=response) as request:
            provider = GeminiProvider(api_key="secret-test-key")
            self.assertEqual(provider.generate("system", "user"), "OK")

        sent_request = request.call_args.args[0]
        self.assertNotIn("secret-test-key", sent_request.full_url)
        self.assertEqual(sent_request.get_header("X-goog-api-key"), "secret-test-key")
        self.assertEqual(request.call_args.kwargs["timeout"], 45)

    def test_retries_transient_503_then_succeeds(self):
        error = HTTPError(
            "https://generativelanguage.googleapis.com/test",
            503,
            "Service Unavailable",
            {},
            io.BytesIO(b'{"error":{"message":"busy"}}'),
        )
        response = FakeResponse(
            b'{"candidates":[{"content":{"parts":[{"text":"Recovered"}]}}]}'
        )
        with patch("company.llm.urlopen", side_effect=[error, response]) as request, patch(
            "company.llm.time.sleep"
        ) as sleep:
            provider = GeminiProvider(api_key="secret-test-key")
            self.assertEqual(provider.generate("system", "user"), "Recovered")

        self.assertEqual(request.call_count, 2)
        sleep.assert_called_once_with(5)

    def test_429_is_not_blindly_retried_and_records_quota_id(self):
        error = HTTPError(
            "https://generativelanguage.googleapis.com/test",
            429,
            "Too Many Requests",
            {},
            io.BytesIO(
                b'{"error":{"message":"Quota exceeded","details":[{"quotaFailure":{"violations":[{"quotaId":"GenerateRequestsPerDay-FreeTier"}]}}]}}'
            ),
        )
        with patch("company.llm.urlopen", side_effect=error) as request, patch(
            "company.llm.time.sleep"
        ) as sleep:
            provider = GeminiProvider(api_key="secret-test-key")
            with self.assertRaises(GeminiAPIError) as raised:
                provider.generate("system", "user")

        self.assertIn("HTTP 429", str(raised.exception))
        self.assertIn("GenerateRequestsPerDay-FreeTier", str(raised.exception))
        self.assertNotIn("secret-test-key", str(raised.exception))
        request.assert_called_once()
        sleep.assert_not_called()

    def test_429_records_safe_google_description_and_status(self):
        error = HTTPError(
            "https://generativelanguage.googleapis.com/test",
            429,
            "Too Many Requests",
            {},
            io.BytesIO(
                b'{"error":{"status":"RESOURCE_EXHAUSTED","description":"Project spend cap exceeded","message":"quota","details":[{"@type":"type.googleapis.com/google.rpc.Help"}]}}'
            ),
        )
        with patch("company.llm.urlopen", side_effect=error):
            provider = GeminiProvider(api_key="secret-test-key")
            with self.assertRaises(GeminiAPIError) as raised:
                provider.generate("system", "user")

        message = str(raised.exception)
        self.assertIn("provider_status=RESOURCE_EXHAUSTED", message)
        self.assertIn("description=Project spend cap exceeded", message)
        self.assertIn("details=Help", message)
        self.assertNotIn("secret-test-key", message)

    def test_does_not_retry_invalid_api_key(self):
        error = HTTPError(
            "https://generativelanguage.googleapis.com/test",
            401,
            "Unauthorized",
            {},
            io.BytesIO(b'{"error":{"message":"invalid key"}}'),
        )
        with patch("company.llm.urlopen", side_effect=error) as request:
            provider = GeminiProvider(api_key="secret-test-key")
            with self.assertRaises(GeminiAPIError) as raised:
                provider.generate("system", "user")

        self.assertIn("HTTP 401", str(raised.exception))
        self.assertNotIn("secret-test-key", str(raised.exception))
        request.assert_called_once()


if __name__ == "__main__":
    unittest.main()


class FallbackSearchTests(unittest.TestCase):
    def test_search_fallback_is_explicitly_unverified(self):
        class Primary:
            def generate(self, *_args, **_kwargs):
                raise GeminiAPIError("Gemini API returned HTTP 429; quota exhausted")

        class Fallback:
            def __init__(self):
                self.prompts = None

            def generate(self, system_prompt, user_prompt):
                self.prompts = (system_prompt, user_prompt)
                return "Search terms and evidence checklist."

        fallback = Fallback()
        provider = FallbackProvider(Primary(), fallback)
        output = provider.generate("research role", "find MSP prospects", use_search=True)

        self.assertIn("UNVERIFIED", output)
        self.assertIn("NO WEB SEARCH WAS PERFORMED", output)
        self.assertIn("Do not invent real companies", fallback.prompts[0])
        self.assertIn("do not claim that research was completed", fallback.prompts[1])

    def test_non_search_fallback_keeps_normal_prompt(self):
        class Primary:
            def generate(self, *_args, **_kwargs):
                raise GeminiAPIError("Gemini API returned HTTP 429; quota exhausted")

        class Fallback:
            def generate(self, system_prompt, user_prompt):
                self.prompts = (system_prompt, user_prompt)
                return "fallback"

        fallback = Fallback()
        output = FallbackProvider(Primary(), fallback).generate("system", "user")
        self.assertEqual(output, "fallback")
        self.assertEqual(fallback.prompts, ("system", "user"))


class ProviderSelectionTests(unittest.TestCase):
    def test_groq_is_selected_when_only_groq_key_is_configured(self):
        with patch.dict("os.environ", {"GROQ_API_KEY": "groq-test-key"}, clear=True):
            provider = _get_cloud_provider()
        self.assertIsInstance(provider, GroqProvider)

    def test_gemini_and_groq_create_quota_fallback_chain(self):
        with patch.dict(
            "os.environ",
            {"GEMINI_API_KEY": "gemini-test-key", "GROQ_API_KEY": "groq-test-key"},
            clear=True,
        ):
            provider = _get_cloud_provider()
        self.assertIsInstance(provider, FallbackProvider)
        self.assertIsInstance(provider.primary, GeminiProvider)
        self.assertIsInstance(provider.fallback, GroqProvider)

    def test_no_provider_key_returns_none(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(_get_cloud_provider())


if __name__ == "__main__":
    unittest.main()
