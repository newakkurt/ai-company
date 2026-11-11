# Architecture v0.3

## Components
- Intake: CLI and optional Telegram long polling.
- Telegram security: explicit numeric chat ID allowlist; unauthorized chats are ignored.
- Orchestrator: validates scope and creates task records.
- Agent registry: role descriptions and capability boundaries.
- Task store: local SQLite database with task and event tables.
- Knowledge vault: Markdown / Obsidian-compatible company memory.
- Approval record: records human approval, but does not execute the task.
- QA: evidence, tests, policy review and final report.
- Adapters: GitHub and optional model providers; write operations remain disabled by default.

## Task lifecycle
received -> planned -> assigned -> working -> qa -> approval_required -> approved_for_next_step -> completed

Alternative terminal states: rejected, blocked, failed.

## Project isolation
Each existing project remains in its own repository and deployment. This company stores project metadata and task references. Source code is not copied by default.

## Safety
The CLI and Telegram intake do not call an LLM, execute shell commands, publish, deploy, spend money or connect to network devices. Telegram only accepts messages from configured chat IDs and writes task records to SQLite.

## Milestones
1. [x] Scaffold and local task records.
2. [x] SQLite task store and approval record.
3. [x] Telegram allowlisted task intake.
4. [ ] Agent prompt packs and knowledge vault.
5. [ ] GitHub read-only adapter.
6. [ ] Configurable LLM adapter with free/local-first options.
7. [ ] Controlled write actions via branch + PR.
8. [ ] Web control panel.
