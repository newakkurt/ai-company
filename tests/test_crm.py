import unittest
from unittest.mock import patch

from company.crm import (
    score_company, norm_name, record_mail, suppress_contact, is_suppressed,
    verify_company, update_company_stage, create_offer, list_companies,
    verify_unchecked_companies,
)

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
            if table=="crm_companies":
                return [self.rows["company"]] if self.rows.get("company") and params.get("company_id")==f"eq.{self.rows['company']['company_id']}" else []
            return []
        if method=="POST" and table=="crm_suppressions":
            self.rows["suppress"]=body
            return []
        if method=="POST" and table=="crm_mail_log":
            self.rows["mail"]=body
            return []
        if method=="PATCH":
            if table=="crm_companies" and self.rows.get("company"):
                self.rows["company"].update(body or {})
            return []
        return []

class CRMTests(unittest.TestCase):
    def test_unchecked_company_sources_are_checked_without_human_verification(self):
        class BackfillStore:
            def __init__(self):
                self.rows = [{
                    "company_id": "co-backfill",
                    "company_name": "Acme Networks",
                    "source_url": "https://acme.example/about",
                    "source_validation_status": "not_checked",
                }]
                self.updated = None

            def _request(self, table, method="GET", params=None, body=None, prefer=None):
                params = params or {}
                if method == "GET" and table == "crm_companies":
                    return [dict(row) for row in self.rows
                            if row["source_validation_status"] == params.get("source_validation_status", "eq.not_checked").removeprefix("eq.")]
                if method == "PATCH" and table == "crm_companies":
                    self.updated = (params, body)
                    self.rows[0].update(body or {})
                    return []
                return []

        store = BackfillStore()
        evidence = {
            "source_validation_status": "reachable_match",
            "source_http_status": 200,
            "source_page_title": "Acme Networks",
            "source_checked_at": "2026-11-13T00:00:00+00:00",
            "source_validation_note": "HTTP 200; company-name token found in page text.",
        }
        with patch("company.source_verification.verify_public_source", return_value=evidence) as verify:
            checked = verify_unchecked_companies(store=store, limit=2)
        self.assertEqual(checked, [{"company_id": "co-backfill", "source_validation_status": "reachable_match"}])
        verify.assert_called_once_with("https://acme.example/about", "Acme Networks")
        self.assertEqual(store.updated[0], {"company_id": "eq.co-backfill"})
        self.assertNotIn("source_type", store.updated[1])
        self.assertEqual(store.rows[0]["source_validation_status"], "reachable_match")


    def test_name_normalization(self):
        self.assertEqual(norm_name("ACME Ltd. & Co."),"acme ltd co")
    def test_score_is_bounded_and_explainable(self):
        result=score_company({"need_summary":"network audit","industry":"MSP","source_url":"https://example.com","source_name":"Company site","source_validation_status":"reachable_match","source_type":"human_verified","business_email":"info@example.com","website":"https://example.com","country":"Türkiye","fit_reason":"multi-site network"})
        self.assertEqual(result["score"],100)
        self.assertEqual(sum(result["breakdown"].values()),100)

    def test_human_verification_requires_reachable_source_and_updates_score(self):
        store=FakeStore()
        store.rows["company"]={
            "company_id":"co-1","company_name":"Acme Network","country":"Türkiye",
            "source_url":"https://acmenetwork.com/about","source_name":"Official site",
            "source_validation_status":"reachable_match","source_type":"agent_research_unverified",
            "need_summary":"multi-site network","industry":"MSP","website":"https://acmenetwork.com",
            "business_email":"info@acmenetwork.com","fit_reason":"network audit","score":0,"score_breakdown":{},
        }
        result=verify_company("co-1",store)
        self.assertEqual(result["source_type"],"human_verified")
        self.assertEqual(result["score"],100)

    def test_sales_stage_and_offer_are_blocked_until_human_verification(self):
        store=FakeStore()
        store.rows["company"]={
            "company_id":"co-2","company_name":"Unverified Ltd","source_type":"agent_research_unverified",
            "source_validation_status":"reachable_match","stage":"new",
        }
        with self.assertRaises(PermissionError):
            update_company_stage("co-2","qualified",store)
        with self.assertRaises(PermissionError):
            create_offer("co-2","NetCmd PRO",store)

    def test_unreachable_source_cannot_be_human_verified(self):
        store=FakeStore()
        store.rows["company"]={
            "company_id":"co-3","source_validation_status":"unreachable",
            "source_type":"agent_research_unverified",
        }
        with self.assertRaises(ValueError):
            verify_company("co-3",store)

    def test_company_search_removes_postgrest_filter_grammar(self):
        store=FakeStore()
        list_companies(store, query="Acme),status.eq.failed,or(id.gt.0)")
        params=store.calls[-1][2]
        self.assertEqual(params["or"], "(company_name.ilike.*Acmestatuseqfailedoridgt0*,country.ilike.*Acmestatuseqfailedoridgt0*,industry.ilike.*Acmestatuseqfailedoridgt0*)")

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
