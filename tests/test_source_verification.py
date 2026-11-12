import unittest

from company.source_verification import verify_public_source


PUBLIC_DNS = lambda host, port, type=None: [
    (None, None, None, None, ("93.184.216.34", 443))
]


class FakeResponse:
    def __init__(self, status=200, headers=None, body=b""):
        self.status = status
        self._headers = headers or {"Content-Type": "text/html; charset=utf-8"}
        self._body = body

    def getheader(self, name, default=""):
        return self._headers.get(name, default)

    def read(self, size=-1):
        return self._body[:size]


class FakeConnection:
    def __init__(self, host, ip, timeout=8, response=None):
        self.response = response or FakeResponse(
            body=b"<html><title>Acme Network</title><body>Acme Network provides managed IT services.</body></html>"
        )
        self.requested = None

    def request(self, method, path, headers=None):
        self.requested = (method, path, headers)

    def getresponse(self):
        return self.response

    def close(self):
        pass


class SourceVerificationTests(unittest.TestCase):
    def test_public_https_source_is_checked_and_company_match_is_recorded(self):
        result = verify_public_source(
            "https://acmenetwork.com/about", "Acme Network",
            resolver=PUBLIC_DNS, connection_factory=FakeConnection,
        )
        self.assertEqual(result["source_validation_status"], "reachable_match")
        self.assertEqual(result["source_http_status"], 200)
        self.assertEqual(result["source_page_title"], "Acme Network")

    def test_private_dns_target_is_rejected_before_connect(self):
        def private_dns(host, port, type=None):
            return [(None, None, None, None, ("127.0.0.1", 443))]
        result = verify_public_source(
            "https://public-company.com", "Public Company",
            resolver=private_dns, connection_factory=FakeConnection,
        )
        self.assertEqual(result["source_validation_status"], "unsafe_url")

    def test_placeholder_and_http_urls_are_rejected(self):
        for url in ("http://acme.example.com", "https://acme.example.invalid/page"):
            result = verify_public_source(
                url, "Acme", resolver=PUBLIC_DNS, connection_factory=FakeConnection,
            )
            self.assertEqual(result["source_validation_status"], "unsafe_url")

    def test_reachable_page_without_company_match_stays_unverified(self):
        factory = lambda host, ip, timeout=8: FakeConnection(
            host, ip, timeout,
            FakeResponse(body=b"<html><title>Other company</title><body>Unrelated content</body></html>"),
        )
        result = verify_public_source(
            "https://public-company.com", "Acme Networks",
            resolver=PUBLIC_DNS, connection_factory=factory,
        )
        self.assertEqual(result["source_validation_status"], "reachable_no_match")


if __name__ == "__main__":
    unittest.main()
