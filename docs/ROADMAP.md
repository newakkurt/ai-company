# Roadmap and production gates

Status snapshot: 2026-11-14, after Groq retry fix, scheduler queue repair, Python 3.12 runtime pin, and approval-safe legacy recovery.

## Live integration status

- [x] Approval engine, quota-aware scheduler, durable product releases, CRM source validation, authenticated mail and secure BMC fulfillment are merged into `main`.
- [x] Render deployment for the integrated main branch completed successfully.
- [x] Hosted readiness monitor previously passed: 14 agents, Supabase connected, analysis-only mode. The embedded worker is now intentionally disabled in favor of the scheduled Actions consumer.
- [x] Supabase migrations through `20261112145112_product_download_rpc_security_invoker` were previously applied (20 recorded migrations); the 2026-11-13 performance SQL was applied directly and its idempotent migration file is committed for future environments.
- [x] RLS is enabled on approval, product, mail, CRM, membership and payment tables; latest Supabase security advisor returned zero lints.
- [x] Python 3.10, 3.11 and 3.12 CI passed on commit `10767e37a16dd2319c2183a34914f8dfdedae80b`; product ZIP persistence regression tests are included.
- [x] GitHub Actions is the selected queue consumer; Render embedded worker has been switched off to prevent two consumers racing on the same queue.

## Verified production snapshot

- Render service: `https://ai-company-ferd.onrender.com`; deployment `dep-dbs4d7vj5k9c73ehtar0` is live on commit `858d1495a31fe038cef8254a61624fda19ecd329`. Latest hosted readiness monitor passed at 11:32 UTC+3.
- Render deployment failure root cause: the platform defaulted to Python 3.14.10 while the project CI/runtime target is Python 3.12; the repository now pins Python 3.12 and the subsequent deployment succeeded.
- Worker mode: GitHub Actions scheduled `python -m company.worker --once`; `/readyz` confirms Render worker `enabled=false`, `running=false`, `mode=disabled`, and `worker_mode=github_actions_schedule`.
- Provider: GitHub Actions selected Groq directly (`openai/gpt-oss-20b`). The dedicated task `smoke-groq-provider-20261113-1900` completed with four persisted outputs, proving a real Groq-backed call. The 2026-11-14 worker also selected Groq. A Groq phantom-tool-call HTTP 400 fix is deployed; the affected Instagram draft is eligible for a bounded retry after its 30-minute cooldown. Worker cron `*/5` and manual `workflow_dispatch` are configured; scheduled worker runs have been observed. Render's embedded worker remains off.
- Supabase CRM: 16 companies were checked in bounded batches: 10 `reachable_match`, 2 `reachable_no_match`, 2 `too_large`, 2 `unreachable`. A reachable match is source evidence, not human identity/legal approval; all remain in `new` stage. Live table inspection also shows 16 draft offers, 16 pending follow-ups, and no CRM contacts yet; these are drafts/work items, not qualified customers or sent proposals.
- Queue at latest direct Supabase inspection (2026-11-14 14:27 UTC+3): 19 completed tasks, 23 failed tasks, 0 currently planned tasks, and 15 dead-letter records. All 23 failed tasks are approval-gated; none was manually retried. Historical events and outputs remain retained.
- Commerce: `NetCmd ConfigGuard Lite` (`prd-1cdfbb2727ef`, v1.0.0) remains `review_required`; its rebuilt 6,352-byte ZIP is verified with SHA-256 `6b22dc7716d94df99df0f0596afa4d658ce706741d08e99f77dd169af62ad206`. Offline Docker QA passed (static scan plus 5 tests, network disabled). Payment events, ledger entries, memberships, entitlements and bank settlements remain 0. `/readyz` confirms BMC webhook/product mappings, SMTP and Telegram owner notifications are not configured; mail remains draft-only. No paid sale or buyer delivery has been proven.
- Security advisor: zero lints. Performance advisor: the 10 missing foreign-key indexes and 12 RLS initplan policies are fixed; only 16 informational unused-index notices remain. New FK indexes are intentionally retained for referential integrity and expected future lookups.

## Required before autonomous operation

1. [x] Use GitHub Actions as the sole queue consumer; Render embedded worker has been disabled. Latest workflow logs confirm Supabase and Groq secrets are present.
2. [x] Verify Groq end-to-end: the dedicated Groq smoke task completed with four persisted agent outputs. Worker logs confirm `provider_route=groq` and task completion. The Turkish SEO article and three-email educational sequence were generated and persisted by the content agent in analysis-only mode; neither was published or sent.
3. [ ] Recover only eligible failed/dead-letter tasks in bounded batches after provider verification; preserve all original events and outputs. Approval-required tasks remain blocked. Retry and stale-lease recovery now recheck `approval_required=false` in both selection and conditional update.
4. [x] Run the 16-source verification backfill. Human review is still required for no-match, too-large and unreachable records, and before any outreach.
5. [x] Rebuild, inspect and run offline QA for ConfigGuard Lite 1.0.0 (network disabled, static scan, 5 tests). [ ] Separate human publication approval is still required for exact product ID `prd-1cdfbb2727ef` and SHA-256 `6b22dc7716d94df99df0f0596afa4d658ce706741d08e99f77dd169af62ad206`; the release remains `review_required`.
6. [ ] Owner action: create/confirm the real recurring NetCmd PRO membership in Buy Me a Coffee, copy its actual membership level ID to `BMC_PRO_MEMBERSHIP_LEVEL_ID`, set the same webhook signing secret in BMC and Render, and map verified Shop item IDs to published release IDs/prices. These account-side values cannot be guessed.
7. [ ] Owner action: configure a dedicated support mailbox and SMTP credentials. Keep mail in draft mode until authentication headers and sender limits are validated.
8. [ ] Optional owner action: configure Telegram owner notifications with a company-specific bot/chat; do not reuse unrelated personal bots.
9. [ ] Complete KVKK / ETK / GDPR, consent, suppression, tax, invoice and payout/accounting review before commercial outreach.

## Queue-safety hardening completed on 2026-11-14

- [x] Fix Groq `gpt-oss` phantom tool-call HTTP 400 failures with plain-text-only instructions and bounded retries.
- [x] Allow only fixed scheduler playbooks to opt out of per-task approval; manual/recovery tasks remain approval-gated.
- [x] Add conditional approval checks to failed-task retry and stale-lease recovery updates.
- [x] Migrate only untouched legacy scheduler rows whose deterministic task ID and full description match the playbook; rows with prior claims, failures, retries, dead-letter history, or agent outputs stay gated.
- [x] Add regression tests for approval gates and legacy-task migration; Python 3.10/3.11/3.12 CI passed.
- [x] Restore the approval gate on `auto-marketing-conversion-analysis-2026w46` after prior outputs and human-review escalation were detected.

## Product QA workflow added on 2026-11-14

- [x] Add `.github/workflows/rebuild-configguard-release.yml` to rebuild the exact existing artifact from reviewed repository sources and replace only the stored artifact while preserving `review_required`.
- [x] Add `.github/workflows/product-offline-qa.yml` to verify stored bytes/SHA, scan archive paths/secrets/risky source patterns, and run tests in Docker with `--network none`.
- [x] Rebuild run `43590211991` and QA run `43590240059` both succeeded; the QA run completed 5 tests. Neither workflow publishes or changes release status.
- [ ] Owner: inspect the verified release and approve publication separately against product ID `prd-1cdfbb2727ef` and SHA-256 `6b22dc7716d94df99df0f0596afa4d658ce706741d08e99f77dd169af62ad206`.

## Remaining engineering work

- [ ] Quota-aware deferred retry / dead-letter recovery UI and safe operator controls (the scheduler already has bounded retry logic; operator UI remains missing).
- [ ] CRM source-review UI with evidence, contact legal basis, suppression and human approval.
- [ ] Permission-based one-to-one outreach workflow with bounce/opt-out handling and provider reputation monitoring.
- [ ] Sales dashboard: qualified leads, proposals, payment events, refunds, entitlements and bank settlements.
- [ ] Product version upgrade / license lifecycle and buyer self-service.
- [ ] Durable backup and restore rehearsal for Supabase and product artifacts. No backup/restore rehearsal is currently evidenced.
- [ ] Production monitoring, dead-letter review UI and alert thresholds.
- [x] Add indexes for 10 uncovered foreign keys and convert 12 RLS gate policies to initplan-safe scalar subqueries; advisor confirms no FK-index or RLS-initplan warnings.
- [x] ConfigGuard Lite 1.0.0 isolated runtime QA and static archive/source scan completed.\n- [x] Validate ZIP integrity, CRC, paths, symlinks, encryption, entry/size limits before either local or Supabase product-release persistence; regression tests added. Apply the same offline QA gate to future generated releases.
- [ ] Invoice, VAT, accounting and payout-to-bank reconciliation. These require owner/accountant review and real payout/bank evidence.

A green unit-test run or HTTP health check is not proof of a live sale. Do not mark the company fully operational until the production gates above are completed with real, owner-approved tests.

## 2026-11-14 — Groq TPM quota recovery

- Supabase failure events showed Gemini HTTP 429 quota exhaustion across 25 failed tasks, plus Groq HTTP 413 responses for 2 tasks: the Groq on-demand 8,000 tokens-per-minute budget was exceeded (requests recorded at approximately 10,321 and 10,613 tokens).
- Updated `company/llm.py`: Groq HTTP 413 responses explicitly identified as TPM failures now progressively reduce the user-context excerpt before retrying (preserving the prompt beginning and ending); HTTP 429 continues to use bounded Retry-After/backoff. The retry limit remains 3 total attempts.
- Added a regression test in `tests/test_llm.py` verifying the HTTP 413 retry uses a shorter prompt; removed the obsolete wait-only test.
- Commits: `1c7cee2` (initial retry handling), `529d0a0` and `629599b` (adaptive excerpt and literal correction), `37cc88d` and `d6639eb` (regression test).
- Verification: full Python unit-test suite passed on Python 3.10, 3.11 and 3.12 on commit `10767e37a16dd2319c2183a34914f8dfdedae80b`; Render deployment `dep-dbs4d7vj5k9c73ehtar0` is live and hosted readiness passed. Existing failed tasks were not manually retried; all approval-gated tasks remain untouched.


## 2026-11-14 — Explicit worker provider routing

- [x] Add `AI_COMPANY_PROVIDER=auto|gemini|groq` so the selected provider is deterministic when both credentials exist.
- [x] Pin the scheduled GitHub Actions analysis worker to `AI_COMPANY_PROVIDER=groq`; this prevents a configured Gemini key from silently becoming primary while its quota is exhausted.
- [x] Add regression tests for explicit Groq selection and for refusing to silently fall back to Gemini when the forced Groq key is missing.
- [x] Document the setting in `.env.example`.
- [ ] Confirm the GitHub Actions test run and a successful post-change Groq task before marking this change runtime-verified.
