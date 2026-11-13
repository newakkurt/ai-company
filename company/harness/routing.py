"""Tiered, privacy-first model routing (principle 1).

Tiers
  SMALL_LOCAL  2B-4B local model  : tool use, search, routine sub-tasks
  LARGE_LOCAL  27B-32B local model: planning, coding, instruction following
  CLOUD        frontier model     : generic, non-sensitive blueprints only

Rules
  * Sensitive data (see privacy.scan) is NEVER sent to the cloud tier.
  * Local endpoints must be loopback/private hosts unless explicitly overridden.
  * Only one large local model runs at a time (RAM discipline for 32-48 GB).
  * When nothing eligible is configured the call fails closed with
    PrivacyRoutingError so the caller can escalate to a human.
"""
from __future__ import annotations

import ipaddress
import json
import os
import socket
import threading
from dataclasses import dataclass, field
from enum import Enum
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .privacy import Finding, scan, summarize


class Tier(str, Enum):
    SMALL_LOCAL = "small_local"
    LARGE_LOCAL = "large_local"
    CLOUD = "cloud"


class TaskKind(str, Enum):
    TOOL_USE = "tool_use"
    SEARCH = "search"
    ROUTINE = "routine"
    PLANNING = "planning"
    CODING = "coding"
    INSTRUCTION = "instruction"
    BLUEPRINT = "blueprint"


KIND_TO_TIER = {
    TaskKind.TOOL_USE: Tier.SMALL_LOCAL,
    TaskKind.SEARCH: Tier.SMALL_LOCAL,
    TaskKind.ROUTINE: Tier.SMALL_LOCAL,
    TaskKind.PLANNING: Tier.LARGE_LOCAL,
    TaskKind.CODING: Tier.LARGE_LOCAL,
    TaskKind.INSTRUCTION: Tier.LARGE_LOCAL,
    TaskKind.BLUEPRINT: Tier.CLOUD,
}

# Agent role -> default task kind (ids from config/agents.json).
AGENT_KIND = {
    "ceo": TaskKind.PLANNING,
    "chief_of_staff": TaskKind.PLANNING,
    "technology_architect": TaskKind.PLANNING,
    "software_engineer": TaskKind.CODING,
    "network_infrastructure": TaskKind.INSTRUCTION,
    "research_intelligence": TaskKind.SEARCH,
    "marketing_growth": TaskKind.SEARCH,
    "content_communications": TaskKind.ROUTINE,
    "product_business": TaskKind.PLANNING,
    "data_analytics": TaskKind.ROUTINE,
    "memory_knowledge": TaskKind.ROUTINE,
    "qa_testing": TaskKind.INSTRUCTION,
    "security_compliance": TaskKind.INSTRUCTION,
    "finance_revenue_ops": TaskKind.INSTRUCTION,
}

# Fallback order per requested tier. Cloud is appended only when permitted.
_FALLBACK = {
    Tier.SMALL_LOCAL: (Tier.SMALL_LOCAL, Tier.LARGE_LOCAL, Tier.CLOUD),
    Tier.LARGE_LOCAL: (Tier.LARGE_LOCAL, Tier.CLOUD),
    Tier.CLOUD: (Tier.CLOUD, Tier.LARGE_LOCAL),
}


class PrivacyRoutingError(RuntimeError):
    """No provider is eligible for this request (sensitive data / nothing configured)."""


def infer_task_kind(agent_id: str | None, use_search: bool = False) -> TaskKind:
    if use_search:
        return TaskKind.SEARCH
    return AGENT_KIND.get(agent_id or "", TaskKind.ROUTINE)


def is_local_host(url: str, allow_remote: bool = False) -> bool:
    """True when the endpoint host is loopback or a private address."""
    host = urlparse(url).hostname or ""
    if allow_remote:
        return bool(host)
    if host in {"localhost", "ip6-localhost"}:
        return True
    try:
        candidates = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            candidates = [ipaddress.ip_address(info[4][0]) for info in socket.getaddrinfo(host, None)]
        except (socket.gaierror, UnicodeError):
            return False
    return bool(candidates) and all(ip.is_loopback or ip.is_private for ip in candidates)


class LocalProviderError(RuntimeError):
    """Safe local-model error; never includes prompts or keys."""


class LocalProvider:
    """OpenAI-compatible local endpoint (Ollama, llama.cpp server, LM Studio, vLLM)."""

    supports_search = False

    def __init__(self, base_url: str, model: str, timeout: int = 300, api_key: str = "",
                 allow_remote: bool = False):
        self.base_url = (base_url or "").rstrip("/")
        self.model = model or ""
        self.timeout = timeout
        self.api_key = api_key
        if self.base_url and not is_local_host(self.base_url, allow_remote):
            raise ValueError("Local model endpoint must be loopback/private "
                             "(set AI_COMPANY_LOCAL_ALLOW_REMOTE=true to override)")

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.model)

    def generate(self, system_prompt: str, user_prompt: str, use_search: bool = False,
                 max_tokens: int | None = None) -> str:
        if not self.configured:
            raise LocalProviderError("Local model is not configured")
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system_prompt},
                         {"role": "user", "content": user_prompt}],
            "temperature": 0.2,
            "stream": False,
        }
        if max_tokens:
            payload["max_tokens"] = int(max_tokens)
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        request = Request(self.base_url + "/chat/completions",
                          data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise LocalProviderError(f"Local model returned HTTP {int(exc.code)}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise LocalProviderError(f"Local model unreachable ({type(exc).__name__})") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LocalProviderError("Local model returned invalid JSON") from exc
        choices = data.get("choices") or []
        content = ((choices[0].get("message") or {}).get("content") if choices else None)
        if not isinstance(content, str) or not content.strip():
            raise LocalProviderError("Local model returned an empty response")
        return content.strip()


@dataclass
class RouteDecision:
    """Explainable record of one routing choice (contains no prompt content)."""
    task_kind: str
    requested_tier: str
    chosen_tier: str | None
    sensitive: bool
    findings: dict
    search_dropped: bool = False
    skipped: list = field(default_factory=list)  # (tier, reason)
    error: str | None = None

    def as_dict(self) -> dict:
        return {
            "task_kind": self.task_kind, "requested_tier": self.requested_tier,
            "chosen_tier": self.chosen_tier, "sensitive": self.sensitive,
            "findings": self.findings, "search_dropped": self.search_dropped,
            "skipped": [list(item) for item in self.skipped], "error": self.error,
        }


def _flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}


class TieredProvider:
    """Routes each call to the cheapest *eligible* tier; fails closed for sensitive data."""

    tiered = True          # explicit marker (checked with `is True`)
    supports_search = True

    def __init__(self, small=None, large=None, cloud=None, allow_cloud: bool = True,
                 decision_log=None):
        self.providers = {Tier.SMALL_LOCAL: small, Tier.LARGE_LOCAL: large, Tier.CLOUD: cloud}
        self.allow_cloud = allow_cloud
        self.decision_log = decision_log if decision_log is not None else []
        self._large_lock = threading.Semaphore(1)  # one large model in RAM at a time
        self.last_decision: RouteDecision | None = None

    @staticmethod
    def _available(provider) -> bool:
        if provider is None:
            return False
        return getattr(provider, "configured", True)

    def plan(self, kind: TaskKind, text: str, use_search: bool = False):
        """Return (ordered eligible tiers, decision) without calling any model."""
        findings: list[Finding] = scan(text)
        sensitive = bool(findings)
        requested = KIND_TO_TIER[kind]
        decision = RouteDecision(kind.value, requested.value, None, sensitive, summarize(findings))
        order = []
        for tier in _FALLBACK[requested]:
            provider = self.providers.get(tier)
            if not self._available(provider):
                decision.skipped.append((tier.value, "not_configured"))
                continue
            if tier is Tier.CLOUD and sensitive:
                decision.skipped.append((tier.value, "sensitive_data_blocked"))
                continue
            if tier is Tier.CLOUD and not self.allow_cloud:
                decision.skipped.append((tier.value, "cloud_disabled"))
                continue
            order.append(tier)
        if use_search and Tier.CLOUD in order:
            # Live web search is only possible on the cloud tier (and never for sensitive text).
            order.remove(Tier.CLOUD)
            order.insert(0, Tier.CLOUD)
        return order, decision

    def generate(self, system_prompt: str, user_prompt: str, use_search: bool = False,
                 max_tokens: int | None = None, task_kind: TaskKind | None = None) -> str:
        kind = task_kind or (TaskKind.SEARCH if use_search else TaskKind.ROUTINE)
        order, decision = self.plan(kind, system_prompt + "\n" + user_prompt, use_search)
        if not order:
            decision.error = "no_eligible_provider"
            self._record(decision)
            reasons = ", ".join(f"{t}:{r}" for t, r in decision.skipped) or "none configured"
            raise PrivacyRoutingError(f"No eligible model tier ({reasons}); human review required")
        last_error = None
        for tier in order:
            provider = self.providers[tier]
            search_here = use_search and getattr(provider, "supports_search", False)
            decision.search_dropped = bool(use_search and not search_here)
            if tier is Tier.LARGE_LOCAL:
                from .context_gate import (
                    available_memory_gb, estimate_model_gb, fits_in_budget, memory_budget_gb,
                )
                available = available_memory_gb()
                budget = memory_budget_gb()
                if available is not None:
                    budget = min(budget, available)
                params_b = float(os.getenv("AI_COMPANY_LOCAL_LARGE_PARAMS_B", "32"))
                quant_bits = int(os.getenv("AI_COMPANY_LOCAL_QUANT_BITS", "4"))
                reserve = float(os.getenv("AI_COMPANY_MEM_RESERVE_GB", "6"))
                required = estimate_model_gb(params_b, quant_bits)
                if not fits_in_budget(0, required, reserve_gb=reserve, budget_gb=budget):
                    decision.skipped.append((tier.value, "memory_budget_exceeded"))
                    continue
            try:
                if tier is Tier.LARGE_LOCAL:
                    with self._large_lock:
                        output = self._call(provider, system_prompt, user_prompt, search_here, max_tokens)
                else:
                    output = self._call(provider, system_prompt, user_prompt, search_here, max_tokens)
            except Exception as exc:  # noqa: BLE001 - try the next eligible tier
                last_error = exc
                decision.skipped.append((tier.value, "error:" + type(exc).__name__))
                continue
            decision.chosen_tier = tier.value
            self._record(decision)
            if decision.search_dropped:
                output = "[LOCAL ANSWER — NO WEB SEARCH PERFORMED; claims are UNVERIFIED]\n" + output
            return output
        decision.error = "all_eligible_tiers_failed"
        self._record(decision)
        raise last_error  # type: ignore[misc]

    @staticmethod
    def _call(provider, system_prompt, user_prompt, use_search, max_tokens):
        extra = {"max_tokens": max_tokens} if max_tokens is not None else {}
        if use_search:
            return provider.generate(system_prompt, user_prompt, use_search=True, **extra)
        return provider.generate(system_prompt, user_prompt, **extra)

    def _record(self, decision: RouteDecision):
        self.last_decision = decision
        entry = decision.as_dict()
        self.decision_log.append(entry)
        del self.decision_log[:-200]
        print("route: " + json.dumps(entry, ensure_ascii=False, sort_keys=True), flush=True)


def build_local_providers():
    """Create small/large local providers from env (unconfigured ones are None)."""
    allow_remote = _flag("AI_COMPANY_LOCAL_ALLOW_REMOTE")
    timeout = int(os.getenv("AI_COMPANY_LOCAL_TIMEOUT", "300"))
    built = {}
    for tier, prefix in ((Tier.SMALL_LOCAL, "SMALL"), (Tier.LARGE_LOCAL, "LARGE")):
        url = os.getenv(f"AI_COMPANY_LOCAL_{prefix}_URL", "")
        model = os.getenv(f"AI_COMPANY_LOCAL_{prefix}_MODEL", "")
        key = os.getenv(f"AI_COMPANY_LOCAL_{prefix}_API_KEY", "")
        built[tier] = LocalProvider(url, model, timeout, key, allow_remote) if url and model else None
    return built
