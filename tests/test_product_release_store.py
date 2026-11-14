import base64
import hashlib
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from company.store import TaskStore


def make_zip():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README.md", "Safe offline product package.\\n")
    return buffer.getvalue()


class ProductReleaseStoreTests(unittest.TestCase):
    def test_release_artifact_is_durable_and_checksum_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = TaskStore(Path(tmp) / "releases.db")
            artifact = make_zip()
            digest = hashlib.sha256(artifact).hexdigest()
            release = {
                "product_id": "prd-012345abcdef",
                "name": "Network Ops Starter",
                "version": "0.1.0",
                "summary": "Offline-first network audit starter",
                "release_status": "review_required",
                "checksum": digest,
                "download_path": "/tmp/not-persisted.zip",
                "qa": {"runtime_tests": "not_run"},
            }
            saved = store.save_product_release(release, artifact)
            self.assertEqual(saved["sha256"], digest)
            self.assertEqual(saved["artifact_bytes"], len(artifact))
            self.assertEqual(base64.b64decode(saved["artifact_base64"]), artifact)
            self.assertEqual(saved["manifest_json"]["release_status"], "review_required")
            self.assertNotIn("download_path", saved["manifest_json"])
            listed = store.list_product_releases()
            self.assertEqual(listed[0]["product_id"], release["product_id"])
            with self.assertRaises(ValueError):
                store.save_product_release(release, b"tampered")

    def test_corrupt_zip_is_rejected_even_when_checksum_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = TaskStore(Path(tmp) / "corrupt-release.db")
            artifact = b"not-a-valid-zip"
            release = {
                "product_id": "prd-012345abcdef",
                "name": "Network Ops Starter",
                "version": "0.1.0",
                "summary": "Offline-first network audit starter",
                "release_status": "review_required",
                "checksum": hashlib.sha256(artifact).hexdigest(),
            }
            with self.assertRaisesRegex(ValueError, "valid ZIP"):
                store.save_product_release(release, artifact)
            self.assertIsNone(store.get_product_release(release["product_id"]))

    def test_empty_and_oversized_artifacts_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = TaskStore(Path(tmp) / "releases.db")
            release = {
                "product_id": "prd-012345abcdef", "name": "A", "version": "0.1.0",
                "summary": "", "checksum": hashlib.sha256(b"").hexdigest(),
            }
            with self.assertRaises(ValueError):
                store.save_product_release(release, b"")
            with self.assertRaises(ValueError):
                store.save_product_release(release, b"x" * 1_500_001)



    def test_approved_product_entitlement_has_limited_download_token(self):
        import datetime
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            store = TaskStore(Path(tmp) / "fulfillment.db")
            artifact = make_zip()
            digest = hashlib.sha256(artifact).hexdigest()
            release = {
                "product_id": "prd-abcdef123456", "name": "NetCmd PRO",
                "version": "1.0.0", "summary": "Network automation product",
                "release_status": "review_required", "checksum": digest,
            }
            store.save_product_release(release, artifact)
            store.update_product_release_status(release["product_id"], "approved_for_sale")
            created = store.create_product_entitlement(
                "event-1", "subscription-1", release["product_id"],
                "buyer@example.com", "Buyer",
            )
            self.assertTrue(created["created"])
            duplicate = store.create_product_entitlement(
                "event-2", "subscription-1", release["product_id"],
                "buyer@example.com", "Buyer",
            )
            self.assertFalse(duplicate["created"])
            token_hash = hashlib.sha256(b"secret-download-token").hexdigest()
            expires = (datetime.datetime.now(datetime.timezone.utc)
                       + datetime.timedelta(days=7)).isoformat()
            self.assertTrue(store.create_product_download_token(
                created["entitlement"]["entitlement_id"], token_hash, expires, 2
            ))
            self.assertFalse(store.create_product_download_token(
                created["entitlement"]["entitlement_id"],
                hashlib.sha256(b"second-token").hexdigest(), expires, 2
            ))
            first = store.consume_product_download(token_hash)
            second = store.consume_product_download(token_hash)
            third = store.consume_product_download(token_hash)
            self.assertEqual(first["sha256"], digest)
            self.assertEqual(second["sha256"], digest)
            self.assertIsNone(third)
            store.update_product_entitlement_status("subscription-1", "refunded")
            self.assertIsNone(store.consume_product_download(token_hash))

    def test_unpublished_or_expired_products_cannot_be_downloaded(self):
        import datetime
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            store = TaskStore(Path(tmp) / "fulfillment-expired.db")
            artifact = b"zip-product-data"
            digest = hashlib.sha256(artifact).hexdigest()
            release = {
                "product_id": "prd-fedcba654321", "name": "Unpublished",
                "version": "0.1.0", "summary": "", "checksum": digest,
            }
            store.save_product_release(release, artifact)
            ent = store.create_product_entitlement(
                "event-expired", "subscription-expired", release["product_id"], "b@example.com", "B"
            )["entitlement"]
            token_hash = hashlib.sha256(b"expired-token").hexdigest()
            expired = (datetime.datetime.now(datetime.timezone.utc)
                       - datetime.timedelta(days=1)).isoformat()
            store.create_product_download_token(ent["entitlement_id"], token_hash, expired, 5)
            self.assertIsNone(store.consume_product_download(token_hash))

if __name__ == "__main__":
    unittest.main()
