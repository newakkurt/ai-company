# Roadmap

## Phase 0 — Repository foundation
- [x] Repository scaffold, constitution, and approval policy
- [x] Local CLI task intake
- [ ] Windows installation and local tests verified by owner

## Phase 1 — 13-role orchestration foundation
- [x] 14-agent registry with unique roles and capability boundaries
- [x] Read-only CFO role registered and covered by routing/permission tests
- [x] Deterministic task routing and suggested assignments
- [x] SQLite task, assignment, audit, and agent-output records
- [x] Human approval record (record-only; never triggers execution)
- [x] Local company knowledge memory (remember / recall)
- [x] Optional Ollama local-model adapter and analysis runner
- [x] Agent registry and runner unit tests authored
- [ ] End-to-end local model run verified on Windows

## Phase 2 — Safe integrations
- [x] Telegram allowlisted task intake (local task creation only)
- [ ] GitHub read-only project inspection adapter
- [x] Autonomous daily/weekly task scheduler (idempotent; see docs/AUTONOMY_SETUP.md)
- [x] Owner Telegram notifications: verified sales, unexpected payment events, cancellations, daily reports, failures
- [x] Research roles use grounded web search with cited sources
- [x] Inbound-mail triage with draft-first mode, escalation of sensitive topics and guarded opt-in auto-reply
- [x] Bounded automatic retry of failed tasks
- [ ] Durable hosted worker with leases and dead-letter handling (lease + bounded retry done; dead-letter queue open)
- [ ] Structured CRM / prospect store with dedupe, source evidence and opt-out handling
- [ ] Isolated adapters for the user's existing projects
- [ ] QA report and release evidence workflow
- [ ] Optional Obsidian-compatible Markdown export

## Phase 3 — Controlled execution
- [ ] Branch-only code changes with diff review
- [ ] Human-approved PR creation
- [ ] Explicitly approved deployment workflow
- [ ] Web/desktop control panel
- [ ] Usage limits, audit dashboard, backup/restore

No external write or production operation is enabled by this roadmap until its implementation and approval gates are complete.
