import unittest

from company.agents import agent_summary, load_agents, route_task


class AgentRegistryTests(unittest.TestCase):
    def test_registry_has_exactly_14_unique_agents(self):
        agents = load_agents()
        self.assertEqual(len(agents), 14)
        self.assertEqual(len({agent.id for agent in agents}), 14)
        self.assertIn("ceo", {agent.id for agent in agents})

    def test_all_agents_require_approval(self):
        self.assertTrue(all(agent.approval_required for agent in load_agents()))

    def test_network_task_routes_to_network_specialist(self):
        routed = route_task("Huawei switch SNMP network audit")
        self.assertEqual(routed[0], "ceo")
        self.assertIn("network_infrastructure", routed)

    def test_unknown_task_still_has_ceo_owner(self):
        self.assertEqual(route_task("an unrelated unusual request")[0], "ceo")

    def test_summary_does_not_expose_secrets(self):
        summary = agent_summary()
        self.assertEqual(len(summary), 14)
        self.assertTrue(all("token" not in item for item in summary))


if __name__ == "__main__":
    unittest.main()
