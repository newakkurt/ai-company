# Roadmap and production gates

Status snapshot: 2026-11-13, after Supabase URL repair and worker-mode correction.

## Live integration status

- [x] Approval engine, quota-aware scheduler, durable product releases, CRM source validation, authenticated mail and secure BMC fulfillment are merged into `main`.
- [x] Render deployment for the integrated main branch completed successfully.
- [x] Hosted readiness monitor previously passed: 14 agents, Supabase connected, analysis-only mode. The embedded worker is now intentionally disabled in favor of the scheduled Actions consumer.
- [x] Supabase migrations through `20261112145112_product_download_rpc_security_invoker` were previously applied (20 recorded migrations); the 2026-11-13 performance SQL was applied directly and its idempotent migration file is committed for future environments.
- [x] RLS is enabled on approval, product, mail, CRM, membership and payment tables; latest Supabase security advisor returned zero lints.
- [x] Python 3.10, 3.11 and 3.12 CI passed on the latest provider-normalization commit.
- [x] GitHub Actions is the selected queue consumer; Render embedded worker has been switched off to prevent two consumers racing on the same queue.

## Verified production snapshot

- Render service: `https://ai-company-ferd.onrender.com`; latest observed deployment is live.
- Worker mode: GitHub Actions scheduled `python -m company.worker --once`; Render embedded worker is configured off.
- Provider: GitHub Actions selects Groq directly (`openai/gpt-oss-20b`); key normalization trims whitespace/quotes, TPM 429s use bounded backoff, and a real CEO smoke task plus content tasks completed. Render web API still reports Gemini only, but its embedded worker is off. Worker cron `*/5` is configured and manual `workflow_dispatch` is enabled; push-triggered runs passed, but no `schedule`-event run was observed in this audit window, so confirm the workflow is enabled in GitHub Actions.
- Supabase CRM: 16 companies were checked in bounded batches: 10 `reachable_match`, 2 `reachable_no_match`, 2 `too_large`, 2 `unreachable`. A reachable match is source evidence, not human identity/legal approval; all remain in `new` stage.
- Queue at last database inspection: 9 completed tasks, 15 historical failed tasks, 15 dead-letter records, and 89 agent output rows. The failed/dead-letter history is retained; the two old Gemini-quota approval requests were expired after replacement drafts were generated.
- Commerce: 1 product release remains `review_required`; its persisted ZIP SHA-256 matches the stored bytes, but runtime QA is pending. Payment events, ledger entries, memberships, entitlements and bank settlements are all 0. `/readyz` confirms BMC webhook/product mappings, SMTP and Telegram owner notifications are not configured; mail remains draft-only. No paid sale or buyer delivery has been proven.
- Security advisor: zero lints. Performance advisor: the 10 missing foreign-key indexes and 12 RLS initplan policies are fixed; only 17 informational unused-index notices remain. New FK indexes are intentionally retained for referential integrity and expected future lookups.

## Required before autonomous operation

1. [x] Use GitHub Actions as the sole queue consumer; Render embedded worker has been disabled. Latest workflow logs confirm Supabase and Groq secrets are present.
2. [x] Verify Groq end-to-end: a CEO smoke task generated and persisted an output. The Turkish SEO article and three-email educational sequence were generated and persisted by the content agent in analysis-only mode; neither was published or sent.
3. [ ] Recover failed/dead-letter tasks in bounded batches after provider verification; preserve all original events and outputs.
4. [x] Run the 16-source verification backfill. Human review is still required for no-match, too-large and unreachable records, and before any outreach.
5. [ ] Generate a product release, inspect the ZIP, run it in an isolated QA environment (network disabled, resource/dependency scan), then approve publication against its exact product ID and SHA-256.
6. [ ] Owner action: create/confirm the real recurring NetCmd PRO membership in Buy Me a Coffee, copy its actual membership level ID to `BMC_PRO_MEMBERSHIP_LEVEL_ID`, set the same webhook signing secret in BMC and Render, and map verified Shop item IDs to published release IDs/prices. These account-side values cannot be guessed.
7. [ ] Owner action: configure a dedicated support mailbox and SMTP credentials. Keep mail in draft mode until authentication headers and sender limits are validated.
8. [ ] Optional owner action: configure Telegram owner notifications with a company-specific bot/chat; do not reuse unrelated personal bots.
9. [ ] Complete KVKK / ETK / GDPR, consent, suppression, tax, invoice and payout/accounting review before commercial outreach.

## Remaining engineering work

- [ ] Quota-aware deferred retry / dead-letter recovery UI and safe operator controls (the scheduler already has bounded retry logic; operator UI remains missing).
- [ ] CRM source-review UI with evidence, contact legal basis, suppression and human approval.
- [ ] Permission-based one-to-one outreach workflow with bounce/opt-out handling and provider reputation monitoring.
- [ ] Sales dashboard: qualified leads, proposals, payment events, refunds, entitlements and bank settlements.
- [ ] Product version upgrade / license lifecycle and buyer self-service.
- [ ] Durable backup and restore rehearsal for Supabase and product artifacts.
- [ ] Production monitoring, dead-letter review UI and alert thresholds.
- [x] Add indexes for 10 uncovered foreign keys and convert 12 RLS gate policies to initplan-safe scalar subqueries; advisor confirms no FK-index or RLS-initplan warnings.
- [ ] True isolated runtime QA and supply-chain/dependency scanning for generated ZIPs.
- [ ] Invoice, VAT, accounting and payout-to-bank reconciliation.

A green unit-test run or HTTP health check is not proof of a live sale. Do not mark the company fully operational until the production gates above are completed with real, owner-approved tests.
