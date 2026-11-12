# Architecture v1.0

## Components
- Intake: Windows/Linux CLI and optional Telegram long polling.
- CEO orchestrator: creates task records and routes work to relevant roles.
- Agent registry: 14 role definitions, purposes, capabilities, and tool boundaries in `config/agents.json`.
- Router: transparent keyword scoring; CEO is always included and a bounded set of relevant specialists is suggested.
- Agent runner: Gemini primary with optional Groq fallback; grounded research is used for prospect and market tasks. Outputs are suggestions only.
- Task store: Supabase PostgreSQL in hosted mode (RLS + server-side gate) and SQLite for local development; includes task queue, assignments, agent outputs, approval records, CRM, payment ledger, durable product releases and download entitlements.
- Knowledge memory: local `remember` / `recall` functions.
- Approval engine: stores one-time, scoped approvals and enforces them for product publication and other protected actions.
- Telegram intake: allowlisted task creation only.
- Future adapters: isolated read-only integrations first; write adapters disabled until separately approved.

## 14 roles
CEO / Orchestrator; Chief of Staff / Project Manager; Technology Architect; Software Engineer; Network & Infrastructure Engineer; Research & Intelligence Analyst; Marketing & Growth Lead; Content & Communications Editor; Product & Business Analyst; Data & Analytics Analyst; Memory & Knowledge Curator; QA & Testing Engineer; Security & Compliance Officer; CFO / Finance & Revenue Operations.

## Task lifecycle
received -> planned -> suggested_assignments -> analysis_only -> qa_review -> approval_required -> approved_for_next_step

Alternative states: rejected, blocked, failed. Approval does not itself move a task into execution.

## Model behavior
Role prompts are sent to Gemini, with Groq as an optional fallback. Research roles use grounded web search where configured. The model has no shell or network-device access. Generated code and research remain untrusted until QA and human review. Product factory output is persisted as a review-required ZIP and is not executable or publishable by default.

## Project isolation
NetControl, NetOps, NetCmd, social bots, English Telegram bot, and network automation remain separate repositories and deployments. This company stores references and task metadata only. No project source is copied or modified by default.

## Safety
- Dry-run is the default.
- Telegram accepts only configured numeric chat IDs.
- Secrets are stored only in local environment variables / `.env`.
- No autonomous shell execution, publishing, deployment, spending, deletion, Git writes, or device changes.
- Any future external write requires a narrowly scoped, explicit human approval and an auditable diff.

## Current limitations
- The 14 roles are coordinated prompt/worker roles, not 14 separately hosted model instances.
- Routing is keyword-based, not semantic classification.
- Hosted worker scheduling depends on GitHub Actions secrets; the embedded Render worker is opt-in and must not be enabled alongside another consumer without an intentional capacity plan.
- Product publication requires a scoped owner approval; BMC delivery additionally requires a level-to-product map and configured SMTP.
- Payment ledger entries are provider events/estimates, not confirmed bank settlements or accounting records.
- Prospect outreach remains draft/approval controlled; the system does not send cold sales email autonomously.
- Runtime QA of generated products and an end-to-end paid customer journey must be demonstrated before claiming the company is self-operating.
