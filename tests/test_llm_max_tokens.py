import json
import unittest
from unittest.mock import patch

from company.llm import (
    DEFAULT_MAX_OUTPUT_TOKENS,
    GEMINI_MAX_OUTPUT_TOKENS,
    GROQ_MAX_OUTPUT_TOKENS,
    FallbackProvider,
    GeminiAPIError,
    GeminiProvider,
    GroqProvider,
    clamp_max_tokens,
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


GEMINI_OK = b'{"candidates":[{"content":{"parts":[{"text":"ok"}]}}]}'
GROQ_OK = b'{"choices":[{"message":{"content":"ok"}}]}'


def _sent_payload(urlopen_mock):
    return json.loads(urlopen_mock.call_args.args[0].data.decode("utf-8"))


class ClampTests(unittest.TestCase):
    def test_unset_uses_default(self):
        self.assertEqual(clamp_max_tokens(None, 65536), DEFAULT_MAX_OUTPUT_TOKENS)

    def test_requested_value_is_capped_by_ceiling(self):
        self.assertEqual(clamp_max_tokens(500000, 8000), 8000)

    def test_nonpositive_request_becomes_one(self):
        self.assertEqual(clamp_max_tokens(0, 8000), 1)


class ProviderPayloadTests(unittest.TestCase):
    def test_gemini_default_budget_is_unchanged_for_reports(self):
        with patch("company.llm.urlopen", return_value=FakeResponse(GEMINI_OK)) as urlopen:
            GeminiProvider(api_key="k").generate("s", "u")
        self.assertEqual(_sent_payload(urlopen)["generationConfig"]["maxOutputTokens"], 2048)

    def test_gemini_honours_larger_budget_and_ceiling(self):
        with patch("company.llm.urlopen", return_value=FakeResponse(GEMINI_OK)) as urlopen:
            GeminiProvider(api_key="k").generate("s", "u", max_tokens=32000)
        self.assertEqual(_sent_payload(urlopen)["generationConfig"]["maxOutputTokens"], 32000)
        with patch("company.llm.urlopen", return_value=FakeResponse(GEMINI_OK)) as urlopen:
            GeminiProvider(api_key="k").generate("s", "u", max_tokens=10**7)
        self.assertEqual(
            _sent_payload(urlopen)["generationConfig"]["maxOutputTokens"], GEMINI_MAX_OUTPUT_TOKENS
        )

    def test_groq_budget_is_capped_to_its_ceiling(self):
        with patch("company.llm.urlopen", return_value=FakeResponse(GROQ_OK)) as urlopen:
            GroqProvider(api_key="k").generate("s", "u", max_tokens=32000)
        self.assertEqual(_sent_payload(urlopen)["max_tokens"], GROQ_MAX_OUTPUT_TOKENS)


class FallbackForwardingTests(unittest.TestCase):
    def test_legacy_providers_without_max_tokens_still_work(self):
        class Legacy:
            def generate(self, system_prompt, user_prompt):
                return "legacy"

        self.assertEqual(FallbackProvider(Legacy(), Legacy()).generate("s", "u"), "legacy")

    def test_max_tokens_is_forwarded_to_primary_and_fallback(self):
        seen = []

        class Primary:
            def generate(self, s, u, use_search=False, max_tokens=None):
                seen.append(("primary", max_tokens))
                raise GeminiAPIError("Gemini API returned HTTP 503")

        class Fallback:
            def generate(self, s, u, use_search=False, max_tokens=None):
                seen.append(("fallback", max_tokens))
                return "fallback"

        result = FallbackProvider(Primary(), Fallback()).generate("s", "u", max_tokens=9000)
        self.assertEqual(result, "fallback")
        self.assertEqual(seen, [("primary", 9000), ("fallback", 9000)])


if __name__ == "__main__":
    unittest.main()
