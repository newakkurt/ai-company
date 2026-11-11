import tempfile
import unittest
from pathlib import Path

from company.store import TaskStore


class KnowledgeStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = TaskStore(Path(self.tmp.name) / "knowledge.db")

    def tearDown(self):
        self.tmp.cleanup()

    def test_remember_and_recall(self):
        note_id = self.store.remember("Huawei SNMP", "SNMPv3 authPriv test notes", ["network", "huawei"])
        results = self.store.search_knowledge("huawei SNMP")
        self.assertEqual(results[0]["note_id"], note_id)
        self.assertEqual(results[0]["tags"], ["network", "huawei"])

    def test_empty_knowledge_rejected(self):
        with self.assertRaises(ValueError):
            self.store.remember("", "body")

    def test_search_requires_all_terms(self):
        self.store.remember("NetCmd roadmap", "SEO and API work", ["product"])
        self.assertEqual(self.store.search_knowledge("NetCmd absent"), [])


if __name__ == "__main__":
    unittest.main()
