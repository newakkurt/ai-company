# Roadmap and production gates

Status snapshot: 2026-11-13, after Supabase URL repair and worker-mode correction.

## Live integration status

- [x] Approval engine, quota-aware scheduler, durable product releases, CRM source validation, authenticated mail and secure BMC fulfillment are merged into `main`.
- [x] Render deployment for the integrated main branch completed successfully.
- [x] Hosted readiness monitor previously passed: 14 agents, Supabase connected, analysis-only mode. The embedded worker is now intentionally disabled in favor of the scheduled Actions consumer.
- [x] Supabase migrations through `20261112145112_product_download_rpc_security_invoker` were previously applied (20 recorded migrations); the 2026-11-13 performance SQL was applied directly and its idempotent migration file is committed for future environments.
- [x] RLS is enabled on approval, product, mail, CRM, membership and payment tables; latest Supabase security advisor returned zero lints.
- [x] Python 3.10, 3.11 and 3.12 CI passed on the integrated main commit.
- [x] GitHub Actions is the selected queue consumer; Render embedded worker has been switched off to prevent two consumers racing on the same queue.

## Verified production snapshot

- Render service: `https://ai-company-ferd.onrender.com`; latest observed deployment is live.
- Worker mode: GitHub Actions scheduled `python -m company.worker --once`; Render embedded worker is configured off.
- Provider: latest GitHub Actions log showed `GROQ_API_KEY` present and `GEMINI_API_KEY` empty; the worker therefore selects Groq directly. The previous Gemini 429 belongs to the Render embedded worker before it was switched off.
- Supabase: 16 CRM companies; all 16 remain `not_checked` for source validation and `new` in the pipeline.
- Queue at last database inspection: 6 completed tasks, 16 failed tasks, 15 dead-letter records, 84 agent output rows. Failed tasks are retained for controlled recovery; do not erase their audit history.
- Commerce at last inspection: 1 product release in `review_required`, 0 product entitlements, 0 payment ledger entries, 0 bank settlements. No paid sale or buyer delivery has been proven.
- Security advisor: no current lints reported. Performance advisor recheck after the 2026-11-13 index/RLS changes is pending.

## Required before autonomous operation

1. [x] Use GitHub Actions as the sole queue consumer; Render embedded worker has been disabled. Latest workflow logs confirm Supabase and Groq secrets are present.
2. [ ] Verify the next scheduled run completes a real queued task using Groq; an idle/successful process exit alone is not proof of model generation.
3. [ ] Recover failed/dead-letter tasks in bounded batches after provider verification; preserve all original events and outputs.
4. [ ] Verify the 16 existing CRM sources. A successful HTTP fetch is evidence for review, not proof of company identity; a human must approve the source and legal basis before any outreach.
5. [ ] Generate a product release, inspect the ZIP, run it in an isolated QA environment (network disabled, resource/dependency scan), then approve publication against its exact product ID and SHA-256.
6. [ ] Configure BMC webhook signing secret and map actual Shop item IDs through `BMC_EXTRA_PRODUCT_MAP` (or membership tiers through `BMC_PRODUCT_LEVEL_MAP`) to published release IDs and exact USD prices.
7. [ ] Configure dedicated SMTP credentials and test transactional product delivery. Keep inbound auto-replies in draft mode until trusted authentication headers and sender limits are validated.
8. [ ] Run a controlled end-to-end purchase, webhook retry, download expiry/count, cancellation and refund-revocation test.
9. [ ] Complete KVKK / ETK / GDPR, consent, suppression, tax, invoice and payout/accounting review before commercial outreach.

## Remaining engineering work

- [ ] Quota-aware deferred retry / dead-letter recovery UI and safe operator controls (the scheduler already has bounded retry logic; operator UI remains missing).
- [ ] CRM source-review UI with evidence, contact legal basis, suppression and human approval.
- [ ] Permission-based one-to-one outreach workflow with bounce/opt-out handling and provider reputation monitoring.
- [ ] Sales dashboard: qualified leads, proposals, payment events, refunds, entitlements and bank settlements.
- [ ] Product version upgrade / license lifecycle and buyer self-service.
- [ ] Durable backup and restore rehearsal for Supabase and product artifacts.
- [ ] Production monitoring, dead-letter review UI and alert thresholds.
- [x] Add indexes for 10 uncovered foreign keys and convert 12 RLS gate policies to initplan-safe scalar subqueries (database changes applied; advisor recheck pending).
- [ ] True isolated runtime QA and supply-chain/dependency scanning for generated ZIPs.
- [ ] Invoice, VAT, accounting and payout-to-bank reconciliation.

A green unit-test run or HTTP health check is not proof of a live sale. Do not mark the company fully operational until the production gates above are completed with real, owner-approved tests.
