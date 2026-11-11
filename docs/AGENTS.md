# 14-Agent Operating Model

The registry in `config/agents.json` defines exactly 14 specialist roles. The current release implements an offline registry and transparent keyword-based routing. It does **not** claim that 14 independent LLM workers are already reasoning or executing in the background.

## Roles

1. CEO / Orchestrator — company priorities, triage, delegation, decision briefs.
2. Chief of Staff / Project Manager — milestones, dependencies, ownership, progress.
3. Technology Architect — architecture, stack choices, interfaces, integrations.
4. Software Engineer — implementation plans, code review, refactor planning.
5. Network & Infrastructure Engineer — network, systems, devices, infrastructure.
6. Research & Intelligence Analyst — evidence, sources, comparisons, uncertainty.
7. Marketing & Growth Lead — positioning, SEO, acquisition, growth experiments.
8. Content & Communications Editor — documentation, social copy, localization.
9. Product & Business Analyst — requirements, prioritization, business cases.
10. Data & Analytics Analyst — metrics, data quality, reporting.
11. Memory & Knowledge Curator — decisions, lessons, project knowledge.
12. QA & Testing Engineer — acceptance criteria, test plans, regression, release review.
13. Security & Compliance Officer — secrets, privacy, permissions, threat review.
14. CFO / Finance & Revenue Operations — read-only revenue, subscription, fee, refund, churn and settlement reporting from authorized non-secret records; no banking credentials or financial actions.

## Current behavior

- `ai-company agents` lists the registry.
- `ai-company plan DESCRIPTION` creates a dry-run task and records suggested agent assignments.
- Routing is deterministic keyword scoring and is explainable; it is not LLM inference.
- No agent runs shell commands, edits repositories, publishes content, deploys, spends money, deletes data, or changes network devices.
- Suggested assignments are not proof that work was completed.
- All external writes and operational changes require a separate, scoped human approval.

## Next implementation milestones

1. Local task and agent registry (current).
2. Assignment history, knowledge vault, and QA report records.
3. Optional local model adapter (Ollama) behind an explicit setting.
4. Read-only project adapters.
5. Branch/PR-only write adapter with per-action approval.
6. Desktop/web control panel and monitoring.
7. CFO role is registered and test-covered; provider billing connectors and persistent worker remain separate milestones.
