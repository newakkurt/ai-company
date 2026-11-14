import unittest

from company.product_factory import _clean_files


class ProductFactoryPathSafetyTests(unittest.TestCase):
    def test_rejects_posix_and_windows_traversal_paths(self):
        unsafe_paths = (
            "../escape.py",
            "nested/../../escape.py",
            r"..\\escape.py",
            r"C:\\escape.py",
            "C:/escape.py",
            "/tmp/escape.py",
            "bad\x00name.py",
        )
        for path in unsafe_paths:
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    _clean_files({path: "print('not executed')\n"})

    def test_accepts_relative_network_config_examples(self):
        files, warnings = _clean_files({
            "examples/huawei-sample.cfg": "stelnet server enable\n",
            "src/main.py": "def main():\n    return 0\n",
        })
        self.assertIn("examples/huawei-sample.cfg", files)
        self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()
