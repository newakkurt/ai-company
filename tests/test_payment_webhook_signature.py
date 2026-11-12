import hashlib
import hmac
import unittest

from app import _verify_bmc_signature


class BuyMeACoffeeSignatureTests(unittest.TestCase):
    def test_accepts_exact_raw_body_signature(self):
        secret = "unit-test-secret"
        raw = b'{"event_id":123,"type":"membership.started","live_mode":true}'
        signature = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        self.assertTrue(_verify_bmc_signature(raw, secret, signature))

    def test_rejects_modified_body(self):
        secret = "unit-test-secret"
        raw = b'{"event_id":123,"type":"membership.started","live_mode":true}'
        signature = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        self.assertFalse(_verify_bmc_signature(raw + b" ", secret, signature))

    def test_rejects_wrong_secret_and_missing_signature(self):
        raw = b'{"event_id":123}'
        signature = hmac.new(b"correct", raw, hashlib.sha256).hexdigest()
        self.assertFalse(_verify_bmc_signature(raw, "wrong", signature))
        self.assertFalse(_verify_bmc_signature(raw, "correct", ""))


if __name__ == "__main__":
    unittest.main()
