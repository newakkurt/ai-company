import unittest
from unittest.mock import patch

from company.crm import score_company, norm_name, record_mail, suppress_contact, is_suppressed

class FakeStore:
    def __init__(self):
        self.rows = {}
        self.calls = []
    def _request(self, table, method="GET", params=None, body=None, prefer=None):
        self.calls.append((table,method,params,body))
        params=params or {}
        if method=="GET":
            if table=="crm_suppressions":
                return [self.rows["suppress"]] if self.rows.get("suppress") and params.get("normalized_email")==f"eq.{self.rows['suppress']['normalized_email']}" else []
            if table=="crm_contacts":
                return [self.rows["contact"]] if self.rows.get("contact") and params.get("normalized_email")==f"eq.{self.rows['contact']['normalized_email']}" and params.get("do_not_contact")=="eq.true" else []
            return []
        if method=="POST" and table=="crm_suppressions":
            self.rows["suppress"]=body
            return []
        if method=="POST" and table=="crm_mail_log":
            self.rows["mail"]=body
            return []
        if method=="PATCH":
            return []
        return []

class CRMTests(unittest.TestCase):
    def test_name_normalization(self):
        self.assertEqual(norm_name("ACME Ltd. & Co."),"acme ltd co")
    def test_score_is_bounded_and_explainable(self):
        result=score_company({"need_summary":"network audit","industry":"MSP","source_url":"https://example.com","source_name":"Company site","business_email":"info@example.com","website":"https://example.com","country":"Türkiye","fit_reason":"multi-site network"})
        self.assertEqual(result["score"],100)
        self.assertEqual(sum(result["breakdown"].values()),100)
    def test_inbound_unsubscribe_creates_suppression(self):
        store=FakeStore()
        result=record_mail("person@example.com","inbound","Please unsubscribe","Please remove me from your mailing list",store=store)
        self.assertEqual(result["category"],"unsubscribe")
        self.assertTrue(result["do_not_contact"])
        self.assertEqual(store.rows["suppress"]["normalized_email"],"person@example.com")
    def test_manual_suppression_is_global(self):
        store=FakeStore()
        suppress_contact("sales@example.com","requested removal",store=store)
        self.assertTrue(is_suppressed("sales@example.com",store=store))

if __name__=="__main__":
    unittest.main()
