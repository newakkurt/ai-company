# Architecture v1.0

## Components
- Intake: Windows/Linux CLI and optional Telegram long polling.
- CEO orchestrator: creates task records and routes work to relevant roles.
- Agent registry: 14 role definitions, purposes, capabilities, and tool boundaries in `config/agents.json`.
- Router: transparent keyword scoring; CEO is always included, up to four specialists are suggested.
- Agent runner: sends role-specific prompts to an optional local Ollama model; outputs are suggestions only.
- Task store: SQLite tasks, suggested assignments, agent outputs, knowledge notes, and audit events.
- Knowledge memory: local `remember` / `recall` functions.
- Approval record: stores a human decision but never executes the task.
- Telegram intake: allowlisted task creation only.
- Future adapters: isolated read-only integrations first; write adapters disabled until separately approved.

## 14 roles
CEO / Orchestrator; Chief of Staff / Project Manager; Technology Architect; Software Engineer; Network & Infrastructure Engineer; Research & Intelligence Analyst; Marketing & Growth Lead; Content & Communications Editor; Product & Business Analyst; Data & Analytics Analyst; Memory & Knowledge Curator; QA & Testing Engineer; Security & Compliance Officer; CFO / Finance & Revenue Operations.

## Task lifecycle
received -> planned -> suggested_assignments -> analysis_only -> qa_review -> approval_required -> approved_for_next_step

Alternative states: rejected, blocked, failed. Approval does not itself move a task into execution.

## Model behavior
All role prompts are sent to the configured local Ollama model. The model has no tools, shell, repository write access, or network-device access. Outputs must separate facts, assumptions, risks, recommendations, and evidence gaps. Model output is untrusted until reviewed by a human.

## Project isolation
NetControl, NetOps, NetCmd, social bots, English Telegram bot, and network automation remain separate repositories and deployments. This company stores references and task metadata only. No project source is copied or modified by default.

## Safety
- Dry-run is the default.
- Telegram accepts only configured numeric chat IDs.
- Secrets are stored only in local environment variables / `.env`.
- No autonomous shell execution, publishing, deployment, spending, deletion, Git writes, or device changes.
- Any future external write requires a narrowly scoped, explicit human approval and an auditable diff.

## Current limitations
- CFO is a registered read-only reporting role; no billing provider connector or bank access is implemented.
- The 14 roles are a coordinated role framework, not 13 separately hosted model instances.
- Routing is keyword-based, not semantic classification.
- Ollama must be installed and a local model downloaded before `run` can work.
- GitHub, project, and deployment adapters are not implemented yet.
