import unittest

from company.governance import (
    CircuitBreaker, GovernanceError, MAX_RETRIES, MAX_TOTAL_ATTEMPTS,
    classify_task, governance_snapshot, kill_switch_enabled,
    require_safe_model_route, require_agent_profile,
)

class GovernanceTests(unittest.TestCase):
    def test_sensitive_tasks_never_route_to_cloud(self):
        env = {"GEMINI_API_KEY": "present"}
        for text in ("Review customer personal data", "Check an API key", "KVKK payroll export"):
            self.assertNotEqual(classify_task(text).level, "public")
            with self.assertRaises(GovernanceError):
                require_safe_model_route(text, env)

    def test_public_task_can_use_configured_cloud_provider(self):
        self.assertEqual(
            require_safe_model_route("Draft a generic public product overview", {"GROQ_API_KEY": "present"}),
            "cloud_general",
        )

    def test_no_provider_fails_closed(self):
        with self.assertRaises(GovernanceError):
            require_safe_model_route("Write a public generic outline", {})

    def test_kill_switch_is_opt_in(self):
        self.assertFalse(kill_switch_enabled({}))
        self.assertTrue(kill_switch_enabled({"AI_COMPANY_KILL_SWITCH": "true"}))

    def test_attempt_budget_means_three_total_attempts(self):
        self.assertEqual(MAX_TOTAL_ATTEMPTS, 3)
        self.assertEqual(MAX_RETRIES, 2)

    def test_circuit_breaker_opens_and_recovers(self):
        breaker = CircuitBreaker(threshold=2, reset_seconds=10)
        breaker.record_failure(now=100)
        self.assertTrue(breaker.allow_request(now=101))
        breaker.record_failure(now=102)
        self.assertFalse(breaker.allow_request(now=103))
        self.assertEqual(breaker.status(now=103)["state"], "open")
        self.assertTrue(breaker.allow_request(now=113))
        breaker.record_failure(now=114)
        self.assertFalse(breaker.allow_request(now=115))
        breaker.record_success()
        self.assertEqual(breaker.status(now=116)["state"], "closed")

    def test_snapshot_does_not_claim_budget_enforcement(self):
        snapshot = governance_snapshot({"AI_COMPANY_MONTHLY_SPEND_LIMIT_USD": "0"})
        self.assertEqual(snapshot["budget"]["enforcement"], "daily_task_count_only; provider_spend_not_metered")
        self.assertFalse(snapshot["local_model"]["configured"])
    def test_agent_profiles_are_least_privilege(self):
        require_agent_profile("software_engineer", ["implementation_plan", "code_review"], ["repository_read"])
        with self.assertRaises(GovernanceError):
            require_agent_profile("software_engineer", ["implementation_plan"], ["shell"])
        with self.assertRaises(GovernanceError):
            require_agent_profile("unknown_agent", [], [])

if __name__ == "__main__":
    unittest.main()
