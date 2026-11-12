"""Autonomous, bounded work generator.

The worker only consumes tasks; this module is what makes the company produce
work on its own. Every task id is derived from (playbook, day/week), so seeding
is idempotent: restarts, multiple pollers, and Render cold starts can never
create duplicates, and there is no unbounded agent-to-agent task chain.
All seeded tasks are dry-run analysis tasks.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .agents import load_agents
from .dead_letter import archive_if_exhausted

# Turkey has no DST (fixed UTC+3 since 2016); avoids a tzdata dependency on Windows.
TR_TZ = timezone(timedelta(hours=3))
DAILY_START_HOUR = 6

_RULES = (
    " Use public web sources only and cite every external claim with URL and access date."
    " Never fabricate companies, contacts, customers, prices or revenue; mark unknowns explicitly."
    " Do not use login-protected sources or private individuals' personal data."
    " Analysis and drafts only: no sending, publishing, spending or device access."
    " Write the report in Turkish."
)


@dataclass(frozen=True)
class Playbook:
    slug: str
    cadence: str  # "daily" | "weekly"
    agents: tuple[str, ...]
    description: str


PLAYBOOKS: tuple[Playbook, ...] = (
    Playbook(
        "prospects-tr", "daily",
        ("research_intelligence", "marketing_growth", "product_business", "network_infrastructure"),
        "Find up to 10 qualified B2B prospect companies in Turkey (factories, OSB/industrial zones, "
        "ISPs, system integrators, MSPs) that plausibly need network audit / operations tooling. "
        "Output a CRM_LEADS_JSON: [ ... ] block with company_name,country,website,industry,source_name,"
        "source_url,public_contact_channel,need_summary,fit_reason. Only use verified public company "
        "sources and HTTPS source URLs actually opened. Never invent contacts or use personal emails. "
        "Skip companies listed in earlier reports. Also explain qualification evidence."
        + _RULES,
    ),
    Playbook(
        "prospects-global", "daily",
        ("research_intelligence", "marketing_growth", "product_business", "network_infrastructure"),
        "Find up to 10 qualified B2B prospect companies outside Turkey (MSPs, network consultancies, "
        "regional ISPs, enterprise IT teams) that plausibly need multi-vendor network tooling. "
        "Output a CRM_LEADS_JSON: [ ... ] block with company_name,country,website,industry,source_name,"
        "source_url,public_contact_channel,need_summary,fit_reason. Only use verified public company "
        "sources and HTTPS source URLs actually opened. Never invent contacts or use personal emails. "
        "Also explain qualification evidence."
        + _RULES,
    ),
    Playbook(
        "product-opportunities", "daily",
        ("research_intelligence", "product_business", "technology_architect",
         "network_infrastructure", "security_compliance"),
        "Scan public sources for current customer pain points in network operations and rank 3-5 "
        "product ideas by customer value, feasibility, differentiation, support burden, security "
        "risk and time-to-first-revenue. Recommend at most ONE bet to build next with a minimal spec."
        + _RULES,
    ),
    Playbook(
        "content-draft", "daily",
        ("marketing_growth", "content_communications", "network_infrastructure", "qa_testing"),
        "Draft one useful technical post (LinkedIn/X thread or short article) from the current NetCmd "
        "topic area, technically accurate for the vendors it mentions, in Turkish and English. "
        "Draft only; the owner publishes." + _RULES,
    ),
    Playbook(
        "digital-product-factory", "weekly",
        ("research_intelligence", "product_business", "technology_architect",
         "software_engineer", "network_infrastructure", "qa_testing", "security_compliance"),
        "DIGITAL PRODUCT FACTORY: research current network/MSP buyer pains, select ONE narrow "
        "problem with evidence, score urgency/willingness-to-pay/feasibility/differentiation/time-to-revenue/"
        "supportability and security risk, then propose a tiny offline-first MVP specification. "
        "The worker will generate one versioned Python API starter ZIP from these specialist findings. "
        "No device connections, credentials, configuration changes, external contact, publishing or spending."
        + _RULES,
    ),
    Playbook(
        "weekly-review", "weekly",
        ("chief_of_staff", "product_business", "marketing_growth", "data_analytics",
         "qa_testing", "security_compliance", "finance_revenue_ops", "memory_knowledge"),
        "Weekly company review: pick the single highest-value revenue experiment for next week, "
        "list blockers, stale work and risks, and define measurable acceptance criteria. "
        "Report revenue only from records supplied in this task; if none, state that no verified "
        "revenue data was available." + _RULES,
    ),
)


def auto_tasks_enabled() -> bool:
    return os.getenv("AI_COMPANY_AUTO_TASKS", "true").strip().lower() not in {"0", "false", "no", "off"}


def slot_id(playbook: Playbook, now: datetime) -> str:
    local = now.astimezone(TR_TZ)
    if playbook.cadence == "weekly":
        iso = local.isocalendar()
        return f"auto-{playbook.slug}-{iso[0]}w{iso[1]:02d}"
    return f"auto-{playbook.slug}-{local:%Y%m%d}"


def due_playbooks(now: datetime | None = None) -> list[tuple[str, Playbook]]:
    now = now or datetime.now(timezone.utc)
    if now.astimezone(TR_TZ).hour < DAILY_START_HOUR:
        return []
    known = {a.id for a in load_agents()}
    for playbook in PLAYBOOKS:
        unknown = set(playbook.agents) - known
        if unknown:
            raise ValueError(f"Playbook {playbook.slug} references unknown agents: {sorted(unknown)}")
    return [(slot_id(p, now), p) for p in PLAYBOOKS]


def seed_due_tasks(store, now: datetime | None = None) -> list[str]:
    """Create today's/this week's tasks that do not exist yet; retry stuck failures (bounded)."""
    if not auto_tasks_enabled():
        return []
    created = []
    for task_id, playbook in due_playbooks(now):
        existing = store.get_task(task_id)
        if existing is None:
            store.create_task(playbook.description, task_id=task_id)
            store.assign_agents(task_id, ["ceo", *playbook.agents])
            created.append(task_id)
        elif existing["status"] == "failed":
            # Bounded: at most 2 retries, spaced 30 min apart, resumes from saved outputs.
            requeued = store.requeue_failed_task(task_id, max_retries=2, min_age_minutes=30)
            if not requeued:
                # Once the retry budget is exhausted, preserve the complete task
                # snapshot for inspection instead of retrying forever.
                archive_if_exhausted(store, task_id, max_retries=2, min_age_minutes=30)
    if created:
        print(f"scheduler: seeded {len(created)} task(s): {', '.join(created)}", flush=True)
    return created
