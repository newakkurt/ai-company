import unittest
from unittest.mock import Mock

from company.harness import privacy
from company.harness.routing import (
    KIND_TO_TIER, LocalProvider, PrivacyRoutingError, TaskKind, Tier, TieredProvider,
    infer_task_kind, is_local_host,
)

TC = "10000000146"                    # public test number with a valid checksum
CARD = "4111 1111 1111 1111"         # standard Luhn-valid test card
IBAN = "TR33 0006 1005 1978 6457 8413 26"


def fake(name, supports_search=False):
    provider = Mock()
    provider.generate.return_value = f"answer-from-{name}"
    provider.supports_search = supports_search
    provider.configured = True
    return provider


class PrivacyTests(unittest.TestCase):
    def kinds(self, text):
        return {f.kind for f in privacy.scan(text)}

    def test_detects_kvkk_and_financial_data(self):
        self.assertIn("tc_kimlik", self.kinds(f"Müşteri TC {TC}"))
        self.assertIn("payment_card", self.kinds(f"kart {CARD}"))
        self.assertIn("iban", self.kinds(f"IBAN {IBAN}"))
        self.assertIn("phone_tr", self.kinds("Tel: 0532 123 45 67"))
        self.assertIn("email", self.kinds("ali@example.com"))

    def test_detects_secrets_and_internal_network_data(self):
        self.assertIn("api_key", self.kinds("key gsk_abcdefghijklmnopqrstuvwx"))
        self.assertIn("private_key", self.kinds("-----BEGIN RSA PRIVATE KEY-----"))
        self.assertIn("secret_assignment", self.kinds("snmp-agent community read S3cretValue"))
        self.assertIn("internal_ip", self.kinds("switch 10.20.30.40 erişilemiyor"))

    def test_random_numbers_and_plain_text_are_not_flagged(self):
        self.assertEqual(self.kinds("12345678901 ve 4111111111111112 ve public 8.8.8.8"), set())
        self.assertEqual(self.kinds("VLAN 20 için trunk port tasarımı"), set())

    def test_redact_masks_values_and_findings_hold_no_values(self):
        text = f"TC {TC} mail ali@example.com ip 192.168.1.5"
        safe, findings = privacy.redact(text)
        self.assertNotIn(TC, safe)
        self.assertNotIn("ali@example.com", safe)
        self.assertNotIn("192.168.1.5", safe)
        self.assertNotIn(TC, repr(findings))


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.small, self.large, self.cloud = fake("small"), fake("large"), fake("cloud", True)
        self.router = TieredProvider(self.small, self.large, self.cloud)

    def test_tier_mapping_follows_constitution(self):
        self.assertEqual(KIND_TO_TIER[TaskKind.TOOL_USE], Tier.SMALL_LOCAL)
        self.assertEqual(KIND_TO_TIER[TaskKind.SEARCH], Tier.SMALL_LOCAL)
        self.assertEqual(KIND_TO_TIER[TaskKind.CODING], Tier.LARGE_LOCAL)
        self.assertEqual(KIND_TO_TIER[TaskKind.PLANNING], Tier.LARGE_LOCAL)
        self.assertEqual(KIND_TO_TIER[TaskKind.BLUEPRINT], Tier.CLOUD)

    def test_routine_goes_small_planning_goes_large_blueprint_goes_cloud(self):
        self.assertEqual(self.router.generate("s", "u", task_kind=TaskKind.ROUTINE), "answer-from-small")
        self.assertEqual(self.router.generate("s", "u", task_kind=TaskKind.PLANNING), "answer-from-large")
        self.assertEqual(self.router.generate("s", "u", task_kind=TaskKind.BLUEPRINT), "answer-from-cloud")

    def test_sensitive_data_never_reaches_cloud(self):
        only_cloud = TieredProvider(None, None, self.cloud)
        with self.assertRaises(PrivacyRoutingError):
            only_cloud.generate("s", f"TC {TC}", task_kind=TaskKind.BLUEPRINT)
        self.cloud.generate.assert_not_called()
        # With a local model available the same request stays local.
        self.assertEqual(self.router.generate("s", f"TC {TC}", task_kind=TaskKind.BLUEPRINT),
                         "answer-from-large")
        self.cloud.generate.assert_not_called()

    def test_blueprint_never_falls_back_to_cloud_when_disabled(self):
        router = TieredProvider(self.small, self.large, self.cloud, allow_cloud=False)
        self.assertEqual(router.generate("s", "u", task_kind=TaskKind.BLUEPRINT), "answer-from-large")

    def test_falls_back_to_next_eligible_tier_on_error(self):
        self.small.generate.side_effect = RuntimeError("boom")
        self.assertEqual(self.router.generate("s", "u", task_kind=TaskKind.ROUTINE), "answer-from-large")

    def test_search_uses_cloud_only_when_not_sensitive(self):
        out = self.router.generate("s", "güncel fiyatlar", use_search=True, task_kind=TaskKind.SEARCH)
        self.assertEqual(out, "answer-from-cloud")
        out = self.router.generate("s", f"güncel fiyat, TC {TC}", use_search=True, task_kind=TaskKind.SEARCH)
        self.assertTrue(out.startswith("[LOCAL ANSWER"))
        self.assertTrue(self.router.last_decision.search_dropped)

    def test_decision_log_is_explainable_and_contains_no_prompt_content(self):
        self.router.generate("s", f"TC {TC}", task_kind=TaskKind.ROUTINE)
        entry = self.router.decision_log[-1]
        self.assertTrue(entry["sensitive"])
        self.assertEqual(entry["findings"], {"tc_kimlik": 1})
        self.assertNotIn(TC, str(entry))

    def test_agent_roles_map_to_kinds(self):
        self.assertEqual(infer_task_kind("software_engineer"), TaskKind.CODING)
        self.assertEqual(infer_task_kind("research_intelligence", use_search=True), TaskKind.SEARCH)
        self.assertEqual(infer_task_kind("unknown"), TaskKind.ROUTINE)

    def test_local_endpoint_must_be_loopback_or_private(self):
        self.assertTrue(is_local_host("http://127.0.0.1:11434/v1"))
        self.assertTrue(is_local_host("http://192.168.1.20:8080/v1"))
        self.assertFalse(is_local_host("https://8.8.8.8/v1"))
        with self.assertRaises(ValueError):
            LocalProvider("https://8.8.8.8/v1", "m")
        self.assertFalse(LocalProvider("", "").configured)


if __name__ == "__main__":
    unittest.main()
