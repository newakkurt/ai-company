import hashlib
import tempfile
import unittest
from pathlib import Path

from company.store import TaskStore


class ProductReleaseStoreTests(unittest.TestCase):
    def test_release_artifact_is_durable_and_checksum_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = TaskStore(Path(tmp) / "releases.db")
            artifact = b"sample-zip-content"
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
            self.assertEqual(saved["manifest_json"]["release_status"], "review_required")
            self.assertNotIn("download_path", saved["manifest_json"])
            listed = store.list_product_releases()
            self.assertEqual(listed[0]["product_id"], release["product_id"])
            with self.assertRaises(ValueError):
                store.save_product_release(release, b"tampered")

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


if __name__ == "__main__":
    unittest.main()
