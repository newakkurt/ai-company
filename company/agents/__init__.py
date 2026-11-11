"""Registry and safe deterministic routing for the 13 company roles.

Role prompts can be invoked through the optional local-model runner. They are
not autonomous tool-using workers; the registry and router also work offline.
"""
from dataclasses import dataclass
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "config" / "agents.json"


@dataclass(frozen=True)
class Agent:
    id: str
    name: str
    team: str
    purpose: str
    keywords: tuple[str, ...]
    capabilities: tuple[str, ...]
    tools: tuple[str, ...]
    approval_required: bool


def load_agents(path: Path | str = REGISTRY_PATH) -> list[Agent]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    agents = [
        Agent(
            id=item["id"], name=item["name"], team=item["team"],
            purpose=item["purpose"], keywords=tuple(item["keywords"]),
            capabilities=tuple(item["capabilities"]), tools=tuple(item["tools"]),
            approval_required=bool(item["approval_required"]),
        )
        for item in data["agents"]
    ]
    ids = [agent.id for agent in agents]
    if len(agents) != 13:
        raise ValueError(f"Expected exactly 13 agents, found {len(agents)}")
    if len(ids) != len(set(ids)):
        raise ValueError("Agent IDs must be unique")
    if not any(agent.id == "ceo" for agent in agents):
        raise ValueError("CEO orchestrator is required")
    return agents


def route_task(description: str, agents: list[Agent] | None = None) -> list[str]:
    """Return ordered agent IDs using transparent keyword scoring; never executes work."""
    text = re.sub(r"[^a-z0-9ğüşöçıİĞÜŞÖÇ]+", " ", description.casefold())
    words = set(text.split())
    agents = agents or load_agents()
    scores = {}
    for agent in agents:
        if agent.id == "ceo":
            continue
        score = sum(1 for keyword in agent.keywords if keyword.casefold() in words or keyword.casefold() in text)
        if score:
            scores[agent.id] = score
    ordered = sorted(scores, key=lambda key: (-scores[key], key))
    # CEO coordinates every task; specialist roles are suggestions only.
    return ["ceo", *ordered[:4]]


def agent_summary() -> list[dict]:
    return [
        {"id": a.id, "name": a.name, "team": a.team, "purpose": a.purpose,
         "capabilities": list(a.capabilities), "tools": list(a.tools),
         "approval_required": a.approval_required}
        for a in load_agents()
    ]
