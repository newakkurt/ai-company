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
        "prospects-global", "weekly",
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
    Playbook(
        "marketing-seo", "daily",
        ("marketing_growth", "content_communications", "research_intelligence", "network_infrastructure", "qa_testing"),
        "SEO CONTENT STUDIO for NetCmd PRO. Research real search intent for network automation, multi-vendor network management, switch configuration audit, FortiGate/FortiNAC operations, Huawei/Cisco/Aruba automation. Produce one publish-ready Turkish and English SEO article: primary/secondary keywords, intent, non-fabricated SERP observations with source URLs, title, meta description, H1-H3 outline, 1200-1800 word draft, internal-link suggestions, FAQ, schema.org Article/FAQ JSON-LD, image brief, CTA to https://netcmd-site.onrender.com/en/. Avoid keyword stuffing and unsupported superiority claims." + _RULES,
    ),
    Playbook(
        "marketing-linkedin", "daily",
        ("marketing_growth", "content_communications", "network_infrastructure", "qa_testing"),
        "LINKEDIN CONTENT DESK. Create one high-value B2B post for network engineers, IT managers, MSPs and system integrators. Include a strong first-two-line hook, practical technical insight, one example, concise CTA to NetCmd PRO, 3-5 relevant hashtags, Turkish and English versions, suggested carousel outline and alt text. No fake customer stories or results." + _RULES,
    ),
    Playbook(
        "marketing-youtube", "weekly",
        ("marketing_growth", "content_communications", "network_infrastructure", "qa_testing"),
        "YOUTUBE STUDIO. Produce one long-form video package and two Shorts repurposed from it: demand-backed topic, audience/problem, title options, thumbnail concept, 6-10 minute script with timestamps, demo sequence using safe synthetic examples only, description, chapters, tags, pinned comment, CTA, Shorts scripts and captions in Turkish and English. Never claim a real demo was run if it was not." + _RULES,
    ),
    Playbook(
        "marketing-instagram", "daily",
        ("marketing_growth", "content_communications", "network_infrastructure"),
        "INSTAGRAM CONTENT DESK. Produce one carousel or Reel package for NetCmd PRO: concept, opening hook, 6-8 slide copy OR 30-45 second shot-by-shot Reel script, on-screen captions, post caption, accessible alt text, CTA, 5-8 relevant hashtags and Turkish/English variants. Keep technical claims verifiable; no fabricated customer proof." + _RULES,
    ),
    Playbook(
        "marketing-telegram", "daily",
        ("marketing_growth", "content_communications", "product_business"),
        "TELEGRAM ANNOUNCEMENT DESK. Draft one concise Telegram channel announcement that teaches one useful network operations tip and naturally points to NetCmd PRO. Include a short title, readable body, CTA, optional poll question, Turkish and English versions. Do not send it." + _RULES,
    ),
    Playbook(
        "marketing-visual-briefs", "weekly",
        ("marketing_growth", "content_communications", "technology_architect", "qa_testing"),
        "PRODUCT PROMO VISUAL FACTORY. Deliver a coordinated visual campaign brief for NetCmd PRO: one 16:9 hero/banner, one 1:1 Instagram square, one 4:5 feed creative, one 9:16 Story/Reel cover, one LinkedIn carousel cover and one YouTube thumbnail. Specify layout, hierarchy, exact short copy, visual metaphor, brand palette, typography direction, safe margins, accessibility/contrast and image-generation prompts. Use accurate product UI only if verified assets exist; otherwise label mockups as illustrative. Do not invent logos, UI screenshots or customer endorsements." + _RULES,
    ),
    Playbook(
        "marketing-email", "weekly",
        ("marketing_growth", "content_communications", "product_business", "security_compliance"),
        "EMAIL MARKETING STUDIO. Build one permission-based NetCmd PRO nurture campaign: audience eligibility and consent assumptions, subject/preheader A/B options, useful educational email, product proof limited to verified facts, clear $69/month offer framing, CTA, follow-up variant, segmentation and unsubscribe/footer checklist. Draft only; never send. Never use scraped or unconsented lists; flag KVKK/GDPR/İYS review." + _RULES,
    ),
    Playbook(
        "marketing-conversion-analysis", "weekly",
        ("data_analytics", "marketing_growth", "product_business", "finance_revenue_ops"),
        "MARKETING CONVERSION REVIEW. Analyze only available, explicitly supplied analytics, CRM, payment and campaign records. Report funnel stages (visits, signup/leads, qualified leads, trial/demo, checkout, paid, churn/refund), conversion rates only where numerator and denominator exist, channel attribution confidence, drop-offs, cohort observations and 3 prioritized experiments. If tracking integrations/data are absent, list missing metrics and instrumentation plan; never invent traffic, conversion, revenue or CAC." + _RULES,
    ),
    Playbook(
        "marketing-growth-opportunities", "weekly",
        ("research_intelligence", "marketing_growth", "product_business", "data_analytics", "finance_revenue_ops"),
        "WEEKLY GROWTH & MARKET OPPORTUNITY REPORT. Research current network automation, MSP, enterprise network management and adjacent B2B software demand in Turkey and globally. Identify 5 evidence-backed opportunities, competitors/alternatives and source URLs; rank by urgency, willingness-to-pay evidence, reachability, build effort, margin potential and risk. Review actual campaign/CRM/payment data if available; separate verified metrics from hypotheses. Finish with one recommended experiment, owner, 7-day actions, KPI and stop/continue threshold." + _RULES,
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


# Two bounded work items per day: one daily focus and one weekly workstream.
# The global prospect scan is added every other Monday to avoid doubling daily lead work.
DAY_PLAN = {
    0: ("prospects-tr", "digital-product-factory"),
    1: ("product-opportunities", "weekly-review"),
    2: ("marketing-linkedin", "marketing-youtube"),
    3: ("content-draft", "marketing-visual-briefs"),
    4: ("marketing-seo", "marketing-email"),
    5: ("marketing-instagram", "marketing-conversion-analysis"),
    6: ("marketing-telegram", "marketing-growth-opportunities"),
}
FACTORY_SPECIALISTS = (
    "research_intelligence", "product_business", "software_engineer", "qa_testing",
)


def agents_for_playbook(playbook: Playbook) -> list[str]:
    """Keep routine tasks to CEO + two specialists; factory gets four specialists."""
    if playbook.slug == "digital-product-factory":
        specialists = list(FACTORY_SPECIALISTS)
    else:
        specialists = list(playbook.agents[:2])
    return ["ceo", *specialists]


def _is_quota_failure(task: dict) -> bool:
    """Do not hammer an exhausted provider with the ordinary 30-minute retry loop."""
    for event in reversed(task.get("events") or []):
        if event.get("event_type") != "agent_task_failed":
            continue
        details = event.get("details") or {}
        summary = str(details.get("error_summary") or "").upper()
        return "HTTP 429" in summary or "RESOURCE_EXHAUSTED" in summary or "QUOTA" in summary
    return False


def due_playbooks(now: datetime | None = None) -> list[tuple[str, Playbook]]:
    now = now or datetime.now(timezone.utc)
    local = now.astimezone(TR_TZ)
    if local.hour < DAILY_START_HOUR:
        return []
    known = {a.id for a in load_agents()}
    by_slug = {playbook.slug: playbook for playbook in PLAYBOOKS}
    for playbook in PLAYBOOKS:
        unknown = set(playbook.agents) - known
        if unknown:
            raise ValueError(f"Playbook {playbook.slug} references unknown agents: {sorted(unknown)}")
    selected = list(DAY_PLAN[local.weekday()])
    if local.weekday() == 0 and local.isocalendar().week % 2 == 0:
        selected.append("prospects-global")
    return [(slot_id(by_slug[slug], now), by_slug[slug]) for slug in selected]


def seed_due_tasks(store, now: datetime | None = None) -> list[str]:
    """Create today's/this week's tasks that do not exist yet; retry stuck failures (bounded)."""
    if not auto_tasks_enabled():
        return []
    created = []
    for task_id, playbook in due_playbooks(now):
        existing = store.get_task(task_id)
        if existing is None:
            store.create_task(playbook.description, task_id=task_id)
            store.assign_agents(task_id, agents_for_playbook(playbook))
            created.append(task_id)
        elif existing["status"] == "failed":
            # Bounded: at most 2 retries, spaced 30 min apart, resumes from saved outputs.
            quota_failure = _is_quota_failure(existing)
            # Quota failures wait 24h without a fallback provider.
            # Once Groq is configured, resume after 30m and reuse saved outputs.
            retry_limit = 3 if quota_failure else 2
            retry_delay = (30 if os.getenv("GROQ_API_KEY") else 1440) if quota_failure else 30
            requeued = store.requeue_failed_task(
                task_id, max_retries=retry_limit, min_age_minutes=retry_delay
            )
            if not requeued:
                # Preserve the full task snapshot; quota failures wait a full day
                # before one retry rather than repeatedly consuming exhausted quota.
                archive_if_exhausted(
                    store, task_id, max_retries=retry_limit, min_age_minutes=retry_delay
                )
    if created:
        print(f"scheduler: seeded {len(created)} task(s): {', '.join(created)}", flush=True)
    return created
