# Roadmap and production gates

Status snapshot: 2026-11-14, after Groq retry fix, scheduler queue repair, Python 3.12 runtime pin, and approval-safe legacy recovery.

## Live integration status

- [x] Approval engine, quota-aware scheduler, durable product releases, CRM source validation, authenticated mail and secure BMC fulfillment are merged into `main`.
- [x] Render deployment for the integrated main branch completed successfully.
- [x] Hosted readiness monitor previously passed: 14 agents, Supabase connected, analysis-only mode. The embedded worker is now intentionally disabled in favor of the scheduled Actions consumer.
- [x] Supabase migrations through `20261112145112_product_download_rpc_security_invoker` were previously applied (20 recorded migrations); the 2026-11-13 performance SQL was applied directly and its idempotent migration file is committed for future environments.
- [x] RLS is enabled on approval, product, mail, CRM, membership and payment tables; latest Supabase security advisor returned zero lints.
- [x] Python 3.10, 3.11 and 3.12 CI passed on commit `62b1ca7a03d8d8b65ee291d1e852057dd3d464e8`.
- [x] GitHub Actions is the selected queue consumer; Render embedded worker has been switched off to prevent two consumers racing on the same queue.

## Verified production snapshot

- Render service: `https://ai-company-ferd.onrender.com`; deployment `dep-dbs4a6rji66s739jmiog` is live on commit `40887f5a1af09344b6b3f29d9785f69a2c43aa2f`. Render logs confirm application startup, HTTP `/` 200, and `/readyz` 200 at 2026-11-14 11:27 UTC.\n- Render deployment failure root cause: the platform defaulted to Python 3.14.10 while the project CI/runtime target is Python 3.12; the repository now pins Python 3.12 and the subsequent deployment succeeded.
- Worker mode: GitHub Actions scheduled `python -m company.worker --once`; Render embedded worker is configured off.
- Provider: GitHub Actions selected Groq directly (`openai/gpt-oss-20b`). The dedicated task `smoke-groq-provider-20261113-1900` completed with four persisted outputs, proving a real Groq-backed call. The 2026-11-14 worker also selected Groq. A Groq phantom-tool-call HTTP 400 fix is deployed; the affected Instagram draft is eligible for a bounded retry after its 30-minute cooldown. Worker cron `*/5` and manual `workflow_dispatch` are configured; scheduled worker runs have been observed. Render's embedded worker remains off.
- Supabase CRM: 16 companies were checked in bounded batches: 10 `reachable_match`, 2 `reachable_no_match`, 2 `too_large`, 2 `unreachable`. A reachable match is source evidence, not human identity/legal approval; all remain in `new` stage. Live table inspection also shows 16 draft offers, 16 pending follow-ups, and no CRM contacts yet; these are drafts/work items, not qualified customers or sent proposals.
- Queue at latest direct Supabase inspection (2026-11-14 14:27 UTC+3): 19 completed tasks, 23 failed tasks, 0 currently planned tasks, and 15 dead-letter records. All 23 failed tasks are approval-gated; none was manually retried. Historical events and outputs remain retained.
- Commerce: 1 product release remains `review_required`; its persisted ZIP SHA-256 matches the stored bytes, but runtime QA is pending. Payment events, ledger entries, memberships, entitlements and bank settlements are all 0. `/readyz` confirms BMC webhook/product mappings, SMTP and Telegram owner notifications are not configured; mail remains draft-only. No paid sale or buyer delivery has been proven.
- Security advisor: zero lints. Performance advisor: the 10 missing foreign-key indexes and 12 RLS initplan policies are fixed; only 16 informational unused-index notices remain. New FK indexes are intentionally retained for referential integrity and expected future lookups.

## Required before autonomous operation

1. [x] Use GitHub Actions as the sole queue consumer; Render embedded worker has been disabled. Latest workflow logs confirm Supabase and Groq secrets are present.
2. [x] Verify Groq end-to-end: the dedicated Groq smoke task completed with four persisted agent outputs. Worker logs confirm `provider_route=groq` and task completion. The Turkish SEO article and three-email educational sequence were generated and persisted by the content agent in analysis-only mode; neither was published or sent.
3. [ ] Recover only eligible failed/dead-letter tasks in bounded batches after provider verification; preserve all original events and outputs. Approval-required tasks remain blocked. Retry and stale-lease recovery now recheck `approval_required=false` in both selection and conditional update.
4. [x] Run the 16-source verification backfill. Human review is still required for no-match, too-large and unreachable records, and before any outreach.
5. [ ] Generate a product release, inspect the ZIP, run it in an isolated QA environment (network disabled, resource/dependency scan), then approve publication against its exact product ID and SHA-256.
6. [ ] Owner action: create/confirm the real recurring NetCmd PRO membership in Buy Me a Coffee, copy its actual membership level ID to `BMC_PRO_MEMBERSHIP_LEVEL_ID`, set the same webhook signing secret in BMC and Render, and map verified Shop item IDs to published release IDs/prices. These account-side values cannot be guessed.
7. [ ] Owner action: configure a dedicated support mailbox and SMTP credentials. Keep mail in draft mode until authentication headers and sender limits are validated.
8. [ ] Optional owner action: configure Telegram owner notifications with a company-specific bot/chat; do not reuse unrelated personal bots.
9. [ ] Complete KVKK / ETK / GDPR, consent, suppression, tax, invoice and payout/accounting review before commercial outreach.

## Queue-safety hardening completed on 2026-11-14

- [x] Fix Groq `gpt-oss` phantom tool-call HTTP 400 failures with plain-text-only instructions and bounded retries.\n- [x] Allow only fixed scheduler playbooks to opt out of per-task approval; manual/recovery tasks remain approval-gated.\n- [x] Add conditional approval checks to failed-task retry and stale-lease recovery updates.\n- [x] Migrate only untouched legacy scheduler rows whose deterministic task ID and full description match the playbook; rows with prior claims, failures, retries, dead-letter history, or agent outputs stay gated.\n- [x] Add regression tests for approval gates and legacy-task migration; Python 3.10/3.11/3.12 CI passed.\n- [x] Restore the approval gate on `auto-marketing-conversion-analysis-2026w46` after prior outputs and human-review escalation were detected.\n\n## Product QA workflow added on 2026-11-14\n\n- [x] Add a manual GitHub Actions workflow at `.github/workflows/product-offline-qa.yml` to fetch a release by exact product ID, verify stored byte count and SHA-256, scan archive paths/secrets/risky source patterns, and run package tests in a Docker container with `--network none`. It never publishes or changes release status.\n- [ ] Owner: run **Offline Product Release QA** for `prd-1cdfbb2727ef`, inspect the result, then request publication approval against the exact product ID and SHA-256. The release remains `review_required` until that separate approval flow is completed.\n\n## Remaining engineering work

- [ ] Quota-aware deferred retry / dead-letter recovery UI and safe operator controls (the scheduler already has bounded retry logic; operator UI remains missing).
- [ ] CRM source-review UI with evidence, contact legal basis, suppression and human approval.
- [ ] Permission-based one-to-one outreach workflow with bounce/opt-out handling and provider reputation monitoring.
- [ ] Sales dashboard: qualified leads, proposals, payment events, refunds, entitlements and bank settlements.
- [ ] Product version upgrade / license lifecycle and buyer self-service.
- [ ] Durable backup and restore rehearsal for Supabase and product artifacts. No backup/restore rehearsal is currently evidenced.
- [ ] Production monitoring, dead-letter review UI and alert thresholds.
- [x] Add indexes for 10 uncovered foreign keys and convert 12 RLS gate policies to initplan-safe scalar subqueries; advisor confirms no FK-index or RLS-initplan warnings.
- [ ] True isolated runtime QA and supply-chain/dependency scanning for generated ZIPs.
- [ ] Invoice, VAT, accounting and payout-to-bank reconciliation. These require owner/accountant review and real payout/bank evidence.

A green unit-test run or HTTP health check is not proof of a live sale. Do not mark the company fully operational until the production gates above are completed with real, owner-approved tests.

## 2026-11-14 — Groq TPM quota recovery

- Supabase failure events showed Gemini HTTP 429 quota exhaustion across 25 failed tasks, plus Groq HTTP 413 responses for 2 tasks: the Groq on-demand 8,000 tokens-per-minute budget was exceeded (requests recorded at approximately 10,321 and 10,613 tokens).
- Updated `company/llm.py`: Groq HTTP 413 responses explicitly identified as TPM failures now progressively reduce the user-context excerpt before retrying (preserving the prompt beginning and ending); HTTP 429 continues to use bounded Retry-After/backoff. The retry limit remains 3 total attempts.
- Added a regression test in `tests/test_llm.py` verifying the HTTP 413 retry uses a shorter prompt; removed the obsolete wait-only test.
- Commits: `1c7cee2` (initial retry handling), `529d0a0` and `629599b` (adaptive excerpt and literal correction), `37cc88d` and `d6639eb` (regression test).
- Verification limitation: source and test changes were read back from GitHub, but the test suite and hosted worker deployment have not yet been executed/confirmed. Existing failed tasks were not manually retried, and approval-gated tasks remain untouched.
