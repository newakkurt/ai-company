import base64
import hashlib
import unittest
from unittest.mock import patch

import app


class DownloadEndpointTests(unittest.TestCase):
    def test_download_endpoint_hashes_token_and_returns_verified_zip(self):
        artifact = b"zip-data"
        token = "token-value"
        item = {
            "product_id": "prd-abcdef123456", "name": "NetCmd PRO", "version": "1.0.0",
            "artifact_base64": base64.b64encode(artifact).decode("ascii"),
            "sha256": hashlib.sha256(artifact).hexdigest(), "artifact_bytes": len(artifact),
        }

        class FakeStore:
            def __init__(self):
                self.received_hash = None

            def consume_product_download(self, token_hash):
                self.received_hash = token_hash
                return item

        fake = FakeStore()
        with patch.object(app, "store", fake):
            response = app.download_product(token)
        self.assertEqual(fake.received_hash, hashlib.sha256(token.encode()).hexdigest())
        self.assertEqual(response.body, artifact)
        self.assertEqual(response.media_type, "application/zip")
        self.assertEqual(response.headers["cache-control"], "no-store")


if __name__ == "__main__":
    unittest.main()
