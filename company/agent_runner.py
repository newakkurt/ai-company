"""Runs specialist analysis with a local model, then asks CEO to synthesize it."""
from .agents import load_agents, route_task
from .llm import get_provider
from .store import TaskStore

# Roles that need live public-web evidence (companies, competitors, demand).
SEARCH_AGENTS = frozenset({"research_intelligence", "marketing_growth", "product_business"})


def _generate(provider, agent, system_prompt: str, prompt: str) -> str:
    """Use grounded web search for research roles when the provider supports it."""
    use_search = agent.id in SEARCH_AGENTS and getattr(provider, "supports_search", False)
    if getattr(provider, "tiered", False) is True:  # privacy-first tiered routing
        from .harness.routing import infer_task_kind
        return provider.generate(system_prompt, prompt, use_search=use_search,
                                 task_kind=infer_task_kind(agent.id, use_search))
    if use_search:
        return provider.generate(system_prompt, prompt, use_search=True)
    return provider.generate(system_prompt, prompt)


def _checkpoint(output: str) -> str:
    """Verification checkpoint: never persist leaked credentials from a model output."""
    from .harness.escalation import verify_output
    from .harness.privacy import redact
    if verify_output(output, min_chars=0).ok:
        return output
    return redact(output)[0]


def build_system_prompt(agent) -> str:
    capabilities = ", ".join(agent.capabilities)
    return (
        f"You are {agent.name}, part of a 14-role AI company. "
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
    provider = provider or get_provider()
    task = store.get_task(task_id)
    if task is None:
        raise KeyError(f"Task not found: {task_id}")
    if not task["assignments"]:
        store.assign_agents(task_id, route_task(task["description"]))
        task = store.get_task(task_id)

    agents = {agent.id: agent for agent in load_agents()}
    assignments = [a for a in task["assignments"] if a["agent_id"] != "ceo"]
    assignments += [a for a in task["assignments"] if a["agent_id"] == "ceo"]
    persisted = {
        item["agent_id"]: item["output_text"]
        for item in store.list_agent_outputs(task_id)
    }
    results = [
        {"agent_id": assignment["agent_id"], "output": persisted[assignment["agent_id"]]}
        for assignment in assignments
        if assignment["agent_id"] in persisted
    ]
    for assignment in assignments:
        agent = agents.get(assignment["agent_id"])
        if agent is None or agent.id in persisted:
            continue
        # Another worker may have saved this role since we started (e.g. after a
        # lease expiry). Re-check right before paying for another LLM call.
        latest = {item["agent_id"]: item["output_text"] for item in store.list_agent_outputs(task_id)}
        if agent.id in latest:
            persisted[agent.id] = latest[agent.id]
            results.append({"agent_id": agent.id, "output": latest[agent.id]})
            continue
        specialist_context = ""
        if agent.id == "ceo":
            specialist_context = "\n\nSpecialist analysis (unverified suggestions):\n" + "\n\n".join(
                f"[{item['agent_id']}]\n{item['output']}" for item in results
            )
        prompt = (
            f"Task ID: {task_id}\nTask description: {task['description']}\n"
            "Execution mode: dry_run. You are preparing analysis only. "
            "Do not modify files, call external services, publish, deploy, spend money, "
            "delete data, or change network devices."
            f"{specialist_context}"
        )
        print(f"agent_worker: requesting agent={agent.id} task={task_id}", flush=True)
        output = _checkpoint(_generate(provider, agent, build_system_prompt(agent), prompt))
        store.record_agent_output(task_id, agent.id, output)
        print(f"agent_worker: saved agent={agent.id} task={task_id}", flush=True)
        results.append({"agent_id": agent.id, "output": output})
    return results
