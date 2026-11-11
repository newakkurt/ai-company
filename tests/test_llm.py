import io
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from company.llm import GeminiAPIError, GeminiProvider


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
