import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from company.config import load_local_env


class LocalEnvTests(unittest.TestCase):
    def test_loads_values_and_preserves_existing_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("# comment\nA=one\nB='two words'\nINVALID LINE\n", encoding="utf-8")
            with patch.dict(os.environ, {"A": "already"}, clear=True):
                count = load_local_env(path)
                self.assertEqual(os.environ["A"], "already")
                self.assertEqual(os.environ["B"], "two words")
                self.assertEqual(count, 1)

    def test_missing_file_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(load_local_env(Path(directory) / "missing.env"), 0)


if __name__ == "__main__":
    unittest.main()
