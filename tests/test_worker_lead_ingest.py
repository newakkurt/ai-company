"""Regression tests: prospect tasks must ingest CRM_LEADS_JSON without failing.

A function-local ``import json`` once shadowed the module-level import, so any
prospect task whose output contained a lead block died with UnboundLocalError.
"""
import unittest
from unittest.mock import patch

from company.worker import process_one_task


class FakeStore:
    def __init__(self, task_id):
        self.task_id = task_id
        self.completed = None
        self.failed = None

    def claim_next_task(self):
        return self.task_id

    def get_task(self, _task_id):
        return {"task_id": self.task_id, "agent_outputs": []}

    def complete_task(self, _task_id, output_count):
        self.completed = output_count

    def fail_task(self, _task_id, error_type, error_summary=None):
        self.failed = error_type


def _output(leads_json):
    return [{"agent_id": "research_intelligence", "output": "Rapor\nCRM_LEADS_JSON: " + leads_json}]


class LeadIngestTests(unittest.TestCase):
    def _run(self, task_id, leads_json):
        store = FakeStore(task_id)
        with patch("company.worker.run_task", return_value=_output(leads_json)), \
                patch("company.worker.crm_upsert_company") as upsert, \
                patch("company.worker._safe_notify"), \
                patch("company.worker.verify_public_source", return_value={
                    "source_validation_status": "reachable_match",
                    "source_http_status": 200,
                    "source_page_title": "Acme Network",
                    "source_checked_at": "2026-11-12T14:00:00+00:00",
                    "source_validation_note": "HTTP 200; company-name token found in page text.",
                }):
            result = process_one_task(store=store, provider=object())
        return store, result, upsert

    def test_valid_lead_is_ingested_and_task_completes(self):
        leads = ('[{"company_name":"Acme Network","source_name":"Acme",'
                 '"source_url":"https://acme.example.com/about"}]')
        store, result, upsert = self._run("auto-prospects-tr-20261112", leads)
        self.assertEqual(result["status"], "completed")
        self.assertIsNone(store.failed)
        upsert.assert_called_once()
        ingested = upsert.call_args.args[0]
        self.assertEqual(ingested["source_type"], "agent_research_unverified")

    def test_invalid_json_block_is_skipped_without_failing(self):
        store, result, upsert = self._run("crm-research-abc123", "[not valid json")
        self.assertEqual(result["status"], "completed")
        upsert.assert_not_called()

    def test_non_https_or_placeholder_sources_are_rejected(self):
        leads = ('[{"company_name":"Plain Http","source_name":"x","source_url":"http://x.example.com"},'
                 '{"company_name":"Placeholder","source_name":"x",'
                 '"source_url":"https://example.invalid/page"}]')
        store, result, upsert = self._run("auto-prospects-global-20261112", leads)
        self.assertEqual(result["status"], "completed")
        upsert.assert_not_called()


if __name__ == "__main__":
    unittest.main()
