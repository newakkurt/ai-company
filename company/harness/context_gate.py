"""Context gatekeeping and memory discipline (principle 4).

Small models lose accuracy when handed every tool and guideline. select_context()
returns only the tools/guidelines relevant to the current task, within a token
budget that depends on the model tier.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .routing import Tier

ROOT = Path(__file__).resolve().parents[2]

# name -> (keywords, one-line description). Matches ToolBox methods.
TOOL_CATALOG = {
    "read_file": (("oku", "read", "incele", "analiz", "log", "config", "dosya", "inspect", "review"),
                  "Read a text file inside the sandbox (bounded size)."),
    "write_file": (("yaz", "oluştur", "olustur", "create", "write", "üret", "generate", "taslak", "draft"),
                   "Create or overwrite a text file inside the sandbox."),
    "edit_file": (("düzenle", "duzenle", "edit", "değiştir", "degistir", "fix", "düzelt", "refactor", "patch"),
                  "Replace one exact, unique text span in a file."),
    "run_bash": (("çalıştır", "calistir", "run", "test", "build", "komut", "command", "pytest", "unittest"),
                 "Run a safety-checked shell command (disabled unless explicitly enabled)."),
    "search_memory": (("hatırla", "recall", "bilgi", "knowledge", "karar", "decision", "not"),
                      "Search the local knowledge notes."),
}

# Guidelines are the `##` sections of ANAYASA.md; always-on ones keep the hard limits.
ALWAYS_ON = ("Yetki sınırları", "İnsan kontrolü")
TOPIC_KEYWORDS = {
    "Kanıt ve doğruluk": ("kaynak", "araştır", "research", "kanıt", "iddia", "source"),
    "Güvenlik": ("secret", "parola", "token", "güvenlik", "security", ".env", "shell", "key"),
    "Maliyet": ("maliyet", "cost", "ücret", "bütçe", "budget", "spend"),
}

TIER_LIMITS = {  # (max tools, token budget)
    Tier.SMALL_LOCAL: (3, 1200),
    Tier.LARGE_LOCAL: (5, 5000),
    Tier.CLOUD: (5, 8000),
}


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 3)  # conservative for Turkish


def _words(text: str) -> str:
    return re.sub(r"[^\w.]+", " ", (text or "").casefold())


@dataclass
class ContextPlan:
    tools: list = field(default_factory=list)
    guidelines: list = field(default_factory=list)
    dropped: list = field(default_factory=list)
    est_tokens: int = 0

    def render(self) -> str:
        parts = []
        if self.guidelines:
            parts.append("## Rules\n" + "\n\n".join(f"### {t}\n{b}" for t, b in self.guidelines))
        if self.tools:
            parts.append("## Tools\n" + "\n".join(f"- {name}: {desc}" for name, desc in self.tools))
        return "\n\n".join(parts)


def load_guidelines(path: Path | None = None) -> dict[str, str]:
    path = path or ROOT / "ANAYASA.md"
    if not path.is_file():
        return {}
    sections, title, buf = {}, None, []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            if title:
                sections[title] = "\n".join(buf).strip()
            title, buf = line[3:].strip(), []
        elif title:
            buf.append(line)
    if title:
        sections[title] = "\n".join(buf).strip()
    return sections


def select_context(task_text: str, agent_tools: tuple = (), tier: Tier = Tier.SMALL_LOCAL,
                   guidelines: dict | None = None, allowed_tools: set | None = None) -> ContextPlan:
    """Pick relevant tools/guidelines for this task only, within the tier's budget."""
    max_tools, budget = TIER_LIMITS[tier]
    text = _words(task_text)
    guidelines = load_guidelines() if guidelines is None else guidelines
    plan = ContextPlan()

    scored = []
    for name, (keywords, desc) in TOOL_CATALOG.items():
        if allowed_tools is not None and name not in allowed_tools:
            continue
        score = sum(1 for k in keywords if k in text)
        if score:
            scored.append((score, name, desc))
    scored.sort(key=lambda item: (-item[0], item[1]))
    for index, (_score, name, desc) in enumerate(scored):
        (plan.tools.append((name, desc)) if index < max_tools else plan.dropped.append(("tool", name)))

    wanted = list(ALWAYS_ON)
    wanted += [title for title, kws in TOPIC_KEYWORDS.items() if any(k in text for k in kws)]
    used = estimate_tokens(plan.render())
    for title in wanted:
        body = guidelines.get(title)
        if not body:
            continue
        cost = estimate_tokens(title + body)
        if used + cost > budget and title not in ALWAYS_ON:
            plan.dropped.append(("guideline", title))
            continue
        plan.guidelines.append((title, body))
        used += cost
    plan.est_tokens = used
    return plan


# ---- memory discipline --------------------------------------------------------

def estimate_model_gb(params_billion: float, quant_bits: int = 4, context_tokens: int = 8192) -> float:
    """Rough resident size: weights + runtime overhead + KV cache (conservative)."""
    weights = params_billion * quant_bits / 8
    kv = context_tokens / 8192 * (0.5 + params_billion / 16)
    return round(weights * 1.1 + kv + 0.5, 1)


def available_memory_gb() -> float | None:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return round(int(line.split()[1]) / 1024 / 1024, 1)
    except OSError:
        pass
    return None


def memory_budget_gb() -> float:
    return float(os.getenv("AI_COMPANY_MEM_LIMIT_GB", "32"))


def fits_in_budget(loaded_gb: float, new_model_gb: float, reserve_gb: float = 6.0,
                   budget_gb: float | None = None) -> bool:
    """Leave headroom for OS + tooling; refuse to co-load models that would exceed the budget."""
    budget = budget_gb if budget_gb is not None else memory_budget_gb()
    return loaded_gb + new_model_gb + reserve_gb <= budget
