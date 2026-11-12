import unittest
from unittest.mock import patch

from fastapi import HTTPException

import app


class ApiKeyAuthTests(unittest.TestCase):
    def _call(self, header, key="s3cret-key"):
        with patch.dict("os.environ", {"AI_COMPANY_API_KEY": key}):
            return app.require_api_key(authorization=header)

    def test_valid_bearer_key_is_accepted(self):
        self.assertIsNone(self._call("Bearer s3cret-key"))

    def test_wrong_key_is_401(self):
        with self.assertRaises(HTTPException) as ctx:
            self._call("Bearer wrong")
        self.assertEqual(ctx.exception.status_code, 401)

    def test_missing_header_is_401(self):
        with self.assertRaises(HTTPException) as ctx:
            self._call(None)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_non_ascii_header_is_401_not_a_crash(self):
        with self.assertRaises(HTTPException) as ctx:
            self._call("Bearer şifre-é")
        self.assertEqual(ctx.exception.status_code, 401)

    def test_non_ascii_server_key_still_matches(self):
        self.assertIsNone(self._call("Bearer anahtar-ş", key="anahtar-ş"))

    def test_unconfigured_server_key_is_503(self):
        with self.assertRaises(HTTPException) as ctx:
            self._call("Bearer anything", key="")
        self.assertEqual(ctx.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
