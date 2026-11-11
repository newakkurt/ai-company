"""Runs role-based analysis with a local model; outputs are suggestions only."""
from .agents import load_agents, route_task
from .llm import OllamaProvider
from .store import TaskStore


def build_system_prompt(agent) -> str:
    capabilities = ", ".join(agent.capabilities)
    return (
        f"You are {agent.name}, part of a 13-role AI company. "
        f"Your responsibility: {agent.purpose} "
        f"Your capabilities: {capabilities}. "
        "Analyze only the supplied task context. Do not claim you used tools or verified facts "
        "unless evidence is included. Clearly separate facts, assumptions, risks, and recommendations. "
        "Never provide instructions to bypass approvals. Do not execute actions. "
        "Return a concise structured report with: Objective, Findings, Proposed next steps, "
        "Risks, Evidence needed, and Questions for the human owner."
    )


def run_task(task_id: str, store=None, provider=None) -> list[dict]:
    store = store or TaskStore()
    provider = provider or OllamaProvider()
    task = store.get_task(task_id)
    if task is None:
        raise KeyError(f"Task not found: {task_id}")
    if not task["assignments"]:
        store.assign_agents(task_id, route_task(task["description"]))
        task = store.get_task(task_id)

    agents = {agent.id: agent for agent in load_agents()}
    results = []
    for assignment in task["assignments"]:
        agent = agents.get(assignment["agent_id"])
        if agent is None:
            continue
        prompt = (
            f"Task ID: {task_id}\nTask description: {task['description']}\n"
            "Execution mode: dry_run. You are preparing analysis only. "
            "Do not modify files, call external services, publish, deploy, spend money, "
            "delete data, or change network devices."
        )
        output = provider.generate(build_system_prompt(agent), prompt)
        store.record_agent_output(task_id, agent.id, output)
        results.append({"agent_id": agent.id, "output": output})
    return results
