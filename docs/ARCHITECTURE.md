# Architecture v0.2

## Components
- Intake: CLI first; Telegram adapter later.
- Orchestrator: validates scope and creates task records.
- Agent registry: role descriptions and capability boundaries.
- Task store: local SQLite database with task and event tables.
- Knowledge vault: Markdown / Obsidian-compatible company memory.
- Approval record: records human approval, but does not execute the task.
- QA: evidence, tests, policy review and final report.
- Adapters: GitHub, Telegram and optional model providers; disabled until configured.

## Task lifecycle
received -> planned -> assigned -> working -> qa -> approval_required -> approved_for_next_step -> completed

Alternative terminal states: rejected, blocked, failed.

## Project isolation
Each existing project remains in its own repository and deployment. This company stores project metadata and task references. Source code is not copied by default.

## Safety
The initial CLI does not call an LLM, execute shell commands, publish, deploy, spend money or connect to network devices. Approval is an audit record only.

## Milestones
1. [x] Scaffold and local task records.
2. [x] SQLite task store and approval record.
3. [ ] Agent prompt packs and knowledge vault.
4. [ ] GitHub read-only adapter.
5. [ ] Telegram intake.
6. [ ] Configurable LLM adapter with free/local-first options.
7. [ ] Controlled write actions via branch + PR.
