import base64
import asyncio
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



    def test_unpublished_release_keeps_entitlement_pending(self):
        class FakeStore:
            def __init__(self):
                self.token = None
                self.status = None

            def get_product_download_token_for_entitlement(self, _entitlement_id):
                return self.token

            def create_product_download_token(self, entitlement_id, token_hash, expires_at, max_downloads=5):
                self.token = {"token_hash": token_hash}
                return True

            def update_product_entitlement_delivery(self, _entitlement_id, status):
                self.status = status

        fake = FakeStore()
        entitlement = {
            "entitlement_id": "ent-1", "subscription_id": "sub-1",
            "buyer_email": "buyer@example.com", "buyer_name": "Buyer",
            "delivery_status": "pending",
        }
        with patch.object(app, "store", fake):
            status = asyncio.run(app._deliver_product_entitlement(
                entitlement, {"name": "NetCmd PRO", "release_status": "review_required"}
            ))
        self.assertEqual(status, "pending")
        self.assertIsNone(fake.token)

    def test_approved_release_is_delivered_once(self):
        class FakeStore:
            def __init__(self):
                self.token = None
                self.status = None

            def get_product_download_token_for_entitlement(self, _entitlement_id):
                return self.token

            def create_product_download_token(self, entitlement_id, token_hash, expires_at, max_downloads=5):
                self.token = {"token_hash": token_hash}
                return True

            def update_product_entitlement_delivery(self, _entitlement_id, status):
                self.status = status

        fake = FakeStore()
        entitlement = {
            "entitlement_id": "ent-2", "subscription_id": "sub-2",
            "buyer_email": "buyer@example.com", "buyer_name": "Buyer",
            "delivery_status": "pending",
        }
        release = {"name": "NetCmd PRO", "release_status": "approved_for_sale"}
        with patch.object(app, "store", fake), patch("app.send_product_delivery_email", return_value=True) as send:
            status = asyncio.run(app._deliver_product_entitlement(entitlement, release))
            self.assertEqual(status, "sent")
            self.assertEqual(fake.status, "sent")
            self.assertEqual(asyncio.run(app._deliver_product_entitlement(
                {**entitlement, "delivery_status": "sent"}, release
            )), "sent")
        send.assert_called_once()

    def test_publish_route_consumes_owner_approval_for_exact_artifact(self):
        release = {"product_id": "prd-abcdef123456", "sha256": "a" * 64}
        class FakeStore:
            def get_product_release(self, _product_id):
                return release
            def update_product_release_status(self, product_id, status):
                return {**release, "product_id": product_id, "release_status": status}
        with patch.object(app, "store", FakeStore()), patch("app.require_action_approval") as gate:
            result = app.product_factory_publish(
                "prd-abcdef123456", app.ProductPublishInput(approval_id="approval-12345678")
            )
        gate.assert_called_once_with(
            "publish_product", "approval-12345678",
            {"product_id": "prd-abcdef123456", "sha256": "a" * 64},
        )
        self.assertEqual(result["release_status"], "approved_for_sale")

if __name__ == "__main__":
    unittest.main()
