import unittest

from company.product_factory import score_idea, _clean_files


class ProductFactoryTests(unittest.TestCase):
    def test_scoring_is_bounded_and_penalizes_security_risk(self):
        idea = {key: 5 for key in (
            "problem_urgency", "willingness_to_pay", "market_access",
            "feasibility", "differentiation", "time_to_revenue", "supportability"
        )}
        low = score_idea({**idea, "security_risk": 1})
        high = score_idea({**idea, "security_risk": 5})
        self.assertEqual(low["score"], 100)
        self.assertLess(high["score"], low["score"])

    def test_rejects_traversal_and_secrets(self):
        with self.assertRaises(ValueError):
            _clean_files({"../escape.py": "print('x')"})
        with self.assertRaises(ValueError):
            _clean_files({"config.py": "API_KEY = 'abcdefghijk-secret-value'"})

    def test_accepts_valid_python_and_flags_risky_code(self):
        files, warnings = _clean_files({"main.py": "import os\nos.system('whoami')\n"})
        self.assertIn("main.py", files)
        self.assertTrue(warnings)


if __name__ == "__main__":
    unittest.main()
