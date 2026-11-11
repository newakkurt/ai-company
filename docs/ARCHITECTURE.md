# Architecture v0.1

## Components
- Intake: CLI first; Telegram adapter later.
- Orchestrator: validates scope, creates task, routes to agents.
- Agent registry: role descriptions and capability boundaries.
- Task store: JSON files for local prototype; SQLite later if needed.
- Knowledge vault: Markdown / Obsidian-compatible company memory.
- Approval gate: explicit human approval for external or destructive actions.
- QA: evidence, tests, policy review and final report.
- Adapters: GitHub, Telegram and optional model providers; disabled until configured.

## Task lifecycle
received -> planned -> assigned -> working -> qa -> approval_required -> completed

Alternative terminal states: rejected, blocked, failed.

## Project isolation
Each existing project remains in its own repository and deployment. This company stores project metadata and task references. Source code is not copied by default.

## Milestones
1. Scaffold and local task records.
2. Human approval queue and audit log.
3. Agent prompt packs and knowledge vault.
4. GitHub read-only adapter.
5. Telegram intake.
6. Configurable LLM adapter with free/local-first options.
7. Controlled write actions via branch + PR, never direct production mutation.
