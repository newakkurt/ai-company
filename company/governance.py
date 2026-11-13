"""Narrow governance controls for the AI Company worker.

This module is deliberately stdlib-only. It supplies enforceable policy decisions;
it does not pretend that a cloud worker is a local model host.
"""
from __future__ import annotations

import os
import re
import threading
from datetime import datetime, timezone
import time
from dataclasses import dataclass
from typing import Mapping

MAX_TOTAL_ATTEMPTS = 3
MAX_RETRIES = MAX_TOTAL_ATTEMPTS - 1
CIRCUIT_FAILURE_THRESHOLD = 3
CIRCUIT_RESET_SECONDS = 60

# Conservative task-description screening. Actual payloads must also be screened
# at ingestion; this first guard prevents obvious sensitive work reaching cloud LLMs.
_RESTRICTED = re.compile(
    r"\b(api[_ -]?key|access[_ -]?token|password|passwd|private[_ -]?key|"
    r"secret|credential|iban|credit[_ -]?card|bank[_ -]?account|"
    r"tc kimlik|national id|social security|medical record|health record|"
    r"patient|payroll|salary|employee record|customer personal data)\b",
    re.IGNORECASE,
)
_CONFIDENTIAL = re.compile(
    r"\b(internal network|internal topology|production config|"
    r"customer config|customer database|private customer|"
    r"kvkk|gdpr|confidential|restricted data)\b",
    re.IGNORECASE,
)

HIGH_RISK_ACTIONS = frozenset({
    "publish_product", "send_email", "send_campaign", "issue_refund",
    "change_payment", "delete_data", "change_permissions", "deploy_production",
    "execute_shell", "network_device_write", "export_customer_data",
})

AGENT_CAPABILITIES = {
    "ceo": frozenset({"task_triage", "delegation", "decision_brief"}),
    "chief_of_staff": frozenset({"project_breakdown", "dependency_mapping", "status_tracking"}),
    "technology_architect": frozenset({"architecture_review", "technology_assessment", "interface_design"}),
    "software_engineer": frozenset({"implementation_plan", "code_review", "refactor_plan"}),
    "network_infrastructure": frozenset({"network_analysis", "infrastructure_design", "change_plan"}),
    "research_intelligence": frozenset({"research_brief", "source_assessment", "option_comparison"}),
    "marketing_growth": frozenset({"growth_plan", "seo_audit", "campaign_brief"}),
    "content_communications": frozenset({"content_draft", "documentation", "localization"}),
    "product_business": frozenset({"requirements", "prioritization", "business_case"}),
    "data_analytics": frozenset({"metric_design", "data_quality_review", "report_plan"}),
    "memory_knowledge": frozenset({"knowledge_capture", "decision_log", "knowledge_retrieval"}),
    "qa_testing": frozenset({"test_plan", "risk_based_testing", "release_review"}),
    "security_compliance": frozenset({"threat_review", "secret_hygiene", "permission_review"}),
    "finance_revenue_ops": frozenset({"revenue_reconciliation", "subscription_metrics", "fee_analysis", "cashflow_reporting"}),
}

AGENT_TOOLS = {
    "ceo": frozenset({"local_store_read"}),
    "chief_of_staff": frozenset({"local_store_read", "local_store_write"}),
    "technology_architect": frozenset({"local_files_read"}),
    "software_engineer": frozenset({"repository_read"}),
    "network_infrastructure": frozenset({"inventory_read"}),
    "research_intelligence": frozenset({"web_read"}),
    "marketing_growth": frozenset({"analytics_read"}),
    "content_communications": frozenset({"content_read"}),
    "product_business": frozenset({"product_data_read"}),
    "data_analytics": frozenset({"data_read"}),
    "memory_knowledge": frozenset({"knowledge_read", "knowledge_write"}),
    "qa_testing": frozenset({"test_results_read"}),
    "security_compliance": frozenset({"security_config_read"}),
    "finance_revenue_ops": frozenset({"authorized_billing_metadata_read"}),
}

class GovernanceError(RuntimeError):
    """Raised when a task or action violates a mandatory governance rule."""

@dataclass(frozen=True)
class Classification:
    level: str
    reason: str

def classify_task(text: str) -> Classification:
    value = str(text or "")
    if _RESTRICTED.search(value):
        return Classification("restricted", "sensitive_identifier_or_secret_pattern")
    if _CONFIDENTIAL.search(value):
        return Classification("confidential", "internal_or_regulated_context")
    return Classification("public", "no_sensitive_pattern_detected")

def kill_switch_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return str(source.get("AI_COMPANY_KILL_SWITCH", "")).strip().lower() in {"1", "true", "yes", "on"}

def local_model_configured(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return bool(source.get("OLLAMA_BASE_URL") and source.get("AI_COMPANY_LOCAL_MODEL"))

def cloud_route_allowed(classification: Classification, env: Mapping[str, str] | None = None, provider_available: bool = False) -> bool:
    # Cloud is never an allowed route for confidential/restricted task descriptions.
    if classification.level != "public":
        return False
    source = os.environ if env is None else env
    return provider_available or bool(source.get("GEMINI_API_KEY") or source.get("GROQ_API_KEY"))

def require_safe_model_route(text: str, env: Mapping[str, str] | None = None, provider_available: bool = False) -> str:
    classification = classify_task(text)
    if classification.level != "public":
        if local_model_configured(env):
            # The current worker has no Ollama adapter yet; fail closed rather than
            # silently sending sensitive data to Gemini/Groq.
            raise GovernanceError("local_model_adapter_not_implemented")
        raise GovernanceError("sensitive_task_blocked_from_cloud")
    if not cloud_route_allowed(classification, env, provider_available):
        raise GovernanceError("no_allowed_model_provider")
    return "cloud_general"

def require_agent_capability(agent_id: str, capability: str) -> None:
    allowed = AGENT_CAPABILITIES.get(agent_id)
    if allowed is None or capability not in allowed:
        raise GovernanceError("agent_capability_denied")

def require_agent_profile(agent_id: str, capabilities, tools=()) -> None:
    allowed_capabilities = AGENT_CAPABILITIES.get(agent_id)
    allowed_tools = AGENT_TOOLS.get(agent_id)
    if allowed_capabilities is None or allowed_tools is None:
        raise GovernanceError("unknown_agent_denied")
    if not set(capabilities or ()).issubset(allowed_capabilities):
        raise GovernanceError("agent_capability_denied")
    if not set(tools or ()).issubset(allowed_tools):
        raise GovernanceError("agent_tool_denied")

def require_human_approval(action: str) -> None:
    if action in HIGH_RISK_ACTIONS:
        raise GovernanceError("human_approval_required")

def governance_snapshot(env: Mapping[str, str] | None = None) -> dict:
    source = os.environ if env is None else env
    try:
        daily_task_limit = max(1, int(source.get("AI_COMPANY_DAILY_TASK_LIMIT", "20")))
    except (TypeError, ValueError):
        daily_task_limit = 20
    try:
        monthly_spend_limit = max(0.0, float(source.get("AI_COMPANY_MONTHLY_SPEND_LIMIT_USD", "0")))
    except (TypeError, ValueError):
        monthly_spend_limit = 0.0
    return {
        "kill_switch": kill_switch_enabled(source),
        "max_total_attempts": MAX_TOTAL_ATTEMPTS,
        "max_retries": MAX_RETRIES,
        "local_model": {
            "configured": local_model_configured(source),
            "adapter": "not_implemented",
            "sensitive_cloud_fallback": False,
        },
        "cloud_provider": {
            "configured": bool(source.get("GEMINI_API_KEY") or source.get("GROQ_API_KEY")),
            "allowed_for": "public_non_sensitive_tasks_only",
        },
        "budget": {
            "daily_task_limit": daily_task_limit,
            "monthly_spend_limit_usd": monthly_spend_limit,
            "enforcement": "daily_task_count_only; provider_spend_not_metered",
        },
        "external_actions": "human_approval_required",
        "capability_policy": "deny_by_default",
    }

class CircuitBreaker:
    """Thread-safe process-local circuit breaker for a flaky provider."""

    def __init__(self, threshold: int = CIRCUIT_FAILURE_THRESHOLD,
                 reset_seconds: int = CIRCUIT_RESET_SECONDS):
        self.threshold = max(1, int(threshold))
        self.reset_seconds = max(1, int(reset_seconds))
        self._lock = threading.Lock()
        self._failures = 0
        self._opened_at = 0.0

    def allow_request(self, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else now
        with self._lock:
            if self._failures < self.threshold:
                return True
            return current - self._opened_at >= self.reset_seconds

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._opened_at = 0.0

    def record_failure(self, now: float | None = None) -> None:
        current = time.monotonic() if now is None else now
        with self._lock:
            self._failures += 1
            if self._failures >= self.threshold and not self._opened_at:
                self._opened_at = current

    def status(self, now: float | None = None) -> dict:
        current = time.monotonic() if now is None else now
        with self._lock:
            opened = self._failures >= self.threshold
            return {
                "state": "half_open" if opened and current - self._opened_at >= self.reset_seconds
                         else "open" if opened else "closed",
                "failures": self._failures,
                "threshold": self.threshold,
                "reset_seconds": self.reset_seconds,
            }


def block_claimed_task(store, task_id: str, reason: str) -> bool:
    """Move a claimed task to a terminal blocked state and append an audit event."""
    now = datetime.now(timezone.utc).isoformat()
    details = {"reason": str(reason)[:120], "execution": "not_started"}
    if hasattr(store, "_request"):
        changed = store._request(
            "tasks", "PATCH",
            {"task_id": f"eq.{task_id}", "status": "eq.running"},
            {"status": "blocked", "updated_at": now},
            "return=representation",
        )
        if not changed:
            return False
        store._request(
            "assignments", "PATCH",
            {"task_id": f"eq.{task_id}", "status": "in.(suggested,running)"},
            {"status": "blocked"}, "return=minimal",
        )
        store._event(task_id, "agent_task_blocked", "governance", details)
        return True
    with store._connect() as db:
        changed = db.execute(
            "UPDATE tasks SET status='blocked', updated_at=? WHERE task_id=? AND status='running'",
            (now, task_id),
        ).rowcount
        if not changed:
            return False
        db.execute(
            "UPDATE assignments SET status='blocked' WHERE task_id=? AND status IN ('suggested','running')",
            (task_id,),
        )
        store._event(db, task_id, "agent_task_blocked", "governance", details)
        return True
