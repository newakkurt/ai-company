"""Runs specialist analysis with a local model, then asks CEO to synthesize it."""
import os

from .agents import load_agents, route_task
from .llm import get_provider
from .store import TaskStore

# Roles that need live public-web evidence (companies, competitors, demand).
SEARCH_AGENTS = frozenset({"research_intelligence", "marketing_growth", "product_business"})
# Roles that receive the public demand evidence block when the provider cannot browse.
EVIDENCE_AGENTS = SEARCH_AGENTS | {"network_infrastructure"}


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


# Free-tier providers (e.g. Groq on_demand) enforce a small tokens-per-minute budget and answer
# HTTP 413 when the CEO synthesis prompt carries every specialist report in full. Persisted
# outputs stay complete; only the prompt excerpt is bounded. Raise it on a paid tier.
DEFAULT_CEO_CONTEXT_CHARS = 7000
MIN_EXCERPT_CHARS = 600


def ceo_context_budget() -> int:
    try:
        value = int(os.getenv("AI_COMPANY_CEO_CONTEXT_CHARS", DEFAULT_CEO_CONTEXT_CHARS))
    except ValueError:
        value = DEFAULT_CEO_CONTEXT_CHARS
    return max(2000, value)


def build_specialist_context(results: list[dict], budget: int | None = None) -> str:
    """Join specialist outputs for the CEO, splitting the character budget evenly."""
    budget = budget or ceo_context_budget()
    if not results:
        return ""
    per_agent = max(MIN_EXCERPT_CHARS, budget // len(results))
    parts = []
    for item in results:
        text = item["output"]
        if len(text) > per_agent:
            text = text[:per_agent].rstrip() + f"\n…[excerpt: {len(item['output']) - per_agent} more chars omitted]"
        parts.append(f"[{item['agent_id']}]\n{text}")
    return "\n\n".join(parts)


def _checkpoint(output: str) -> str:
    """Verification checkpoint: never persist leaked credentials from a model output."""
    from .harness.escalation import verify_output
    from .harness.privacy import redact
    if verify_output(output, min_chars=0).ok:
        return output
    return redact(output)[0]


def build_system_prompt(agent) -> str:
    capabilities = ", ".join(agent.capabilities)
    if agent.id == "content_communications":
        output_guidance = (
            "When the task requests an article, email, post, script, brief, landing page, "
            "or other content artifact, write the complete requested artifact itself. "
            "Do not substitute a plan, strategy, checklist, outline, or questions for the artifact. "
            "Make safe assumptions, use clearly marked placeholders for unknown facts, and never invent evidence. "
            "Never infer product capabilities from a brand name or from general industry practice. "
            "Only state a product feature as fact when the exact capability is supported by evidence in the supplied task context. "
            "Otherwise write the section as a general operational best practice, or mark the feature [VERIFY IN PRODUCT] without asserting it exists. "
            "Do not invent supported vendors, protocols, automatic discovery, scheduled backups, Git storage, approvals, rollback speed, or report formats. "
            "Put brief quality and verification notes after the complete artifact."
        )
    else:
        output_guidance = (
            "Return a concise structured report with: Objective, Findings, Proposed next steps, "
            "Risks, Evidence needed, and Questions for the human owner."
        )
    return (
        f"You are {agent.name}, part of a 14-role AI company. "
        f"Your responsibility: {agent.purpose} "
        f"Your capabilities: {capabilities}. "
        "Analyze only the supplied task context. Do not claim you used tools or verified facts "
        "unless evidence is included. Clearly separate facts, assumptions, risks, and recommendations. "
        "Never provide instructions to bypass approvals. Do not execute actions. "
        + output_guidance
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
            specialist_context = (
                "\n\nSpecialist analysis (unverified suggestions; excerpts, full text is stored):\n"
                + build_specialist_context(results)
            )
        evidence_context = ""
        if agent.id in EVIDENCE_AGENTS and not getattr(provider, "supports_search", False):
            # No native grounding (e.g. Groq): give research roles real public demand signals
            # as quoted evidence instead of letting them write market claims from memory.
            from .research_sources import demand_evidence_block
            evidence, count = demand_evidence_block()
            print(f"agent_worker: web evidence items={count} agent={agent.id} task={task_id}", flush=True)
            if evidence:
                evidence_context = "\n\n" + evidence
        prompt = (
            f"Task ID: {task_id}\nTask description: {task['description']}\n"
            "Execution mode: dry_run. You are preparing analysis only. "
            "Do not modify files, call external services, publish, deploy, spend money, "
            "delete data, or change network devices."
            f"{evidence_context}"
            f"{specialist_context}"
        )
        print(f"agent_worker: requesting agent={agent.id} task={task_id}", flush=True)
        from .harness.runtime import generate_with_context
        output = _checkpoint(generate_with_context(provider, agent, build_system_prompt(agent), prompt))
        store.record_agent_output(task_id, agent.id, output)
        print(f"agent_worker: saved agent={agent.id} task={task_id}", flush=True)
        results.append({"agent_id": agent.id, "output": output})
    return results
