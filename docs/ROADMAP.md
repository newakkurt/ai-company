# Roadmap and production gates

Status snapshot: 2026-11-12, after integration PRs #28–#36 and Render deployment.

## Live integration status

- [x] Approval engine, quota-aware scheduler, durable product releases, CRM source validation, authenticated mail and secure BMC fulfillment are merged into `main`.
- [x] Render deployment for the integrated main branch completed successfully.
- [x] Hosted readiness monitor passed: 14 agents, Supabase connected, embedded worker enabled/running, analysis-only mode.
- [x] Supabase migrations through `20261112145112_product_download_rpc_security_invoker` are applied (20 migration records).
- [x] RLS is enabled on approval, product, mail, CRM, membership and payment tables; latest Supabase security advisor returned zero lints.
- [x] Python 3.10, 3.11 and 3.12 CI passed on the integrated main commit.
- [x] The Render embedded worker is the active queue consumer. GitHub Actions worker is safely paused because repository Actions secrets are not configured; do not enable both consumers simultaneously.

## Verified production snapshot

- Render service: `https://ai-company-ferd.onrender.com`; latest observed deployment is live.
- Worker: `enabled=true`, `running=true`, `mode=embedded_supabase_poll`, `analysis_only=true`, `external_actions_enabled=false`.
- Provider: Gemini key is configured, but historical tasks hit Gemini HTTP 429 / RESOURCE_EXHAUSTED. Groq fallback must be configured and verified before retrying the failed workload.
- Supabase: 16 CRM companies; all 16 remain `not_checked` for source validation and `new` in the pipeline.
- Queue: 6 completed tasks, 15 failed tasks, 15 dead-letter records, 83 agent output rows.
- Commerce: 0 product releases, 0 product entitlements and 0 payment ledger entries. No paid sale or buyer delivery has been proven.
- Security advisor: no current lints reported.

## Required before autonomous operation

1. [ ] Add a free Groq API key as `GROQ_API_KEY` in Render and confirm `/readyz` reports the Groq fallback as configured. The readiness workflow now treats this fallback as required because Gemini quota exhaustion already stopped the task queue.
2. [ ] Keep exactly one worker consumer active. Current choice: Render embedded worker. If switching to GitHub Actions, add `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_DB_GATE_KEY`, and `GROQ_API_KEY` (plus `GEMINI_API_KEY` if available) as repository Actions secrets, then disable the embedded Render worker in the same controlled change.
3. [ ] Add an owner-approved recovery process for the 15 quota-failed/dead-letter tasks; do not bulk-retry until Groq fallback is confirmed.
4. [ ] Verify the 16 existing CRM sources. A successful HTTP fetch is evidence for review, not proof of company identity; a human must approve the source and legal basis before any outreach.
5. [ ] Generate a product release, inspect the ZIP, run it in an isolated QA environment (network disabled, resource/dependency scan), then approve publication against its exact product ID and SHA-256.
6. [ ] Configure BMC webhook signing secret and map actual Shop item IDs through `BMC_EXTRA_PRODUCT_MAP` (or membership tiers through `BMC_PRODUCT_LEVEL_MAP`) to published release IDs and exact USD prices.
7. [ ] Configure dedicated SMTP credentials and test transactional product delivery. Keep inbound auto-replies in draft mode until trusted authentication headers and sender limits are validated.
8. [ ] Run a controlled end-to-end purchase, webhook retry, download expiry/count, cancellation and refund-revocation test.
9. [ ] Complete KVKK / ETK / GDPR, consent, suppression, tax, invoice and payout/accounting review before commercial outreach.

## Remaining engineering work

- [ ] Quota-aware deferred retry / dead-letter recovery UI and safe operator controls.
- [ ] CRM source-review UI with evidence, contact legal basis, suppression and human approval.
- [ ] Permission-based one-to-one outreach workflow with bounce/opt-out handling and provider reputation monitoring.
- [ ] Sales dashboard: qualified leads, proposals, payment events, refunds, entitlements and bank settlements.
- [ ] Product version upgrade / license lifecycle and buyer self-service.
- [ ] Durable backup and restore rehearsal for Supabase and product artifacts.
- [ ] Production monitoring, dead-letter review UI and alert thresholds.
- [ ] True isolated runtime QA and supply-chain/dependency scanning for generated ZIPs.
- [ ] Invoice, VAT, accounting and payout-to-bank reconciliation.

A green unit-test run or HTTP health check is not proof of a live sale. Do not mark the company fully operational until the production gates above are completed with real, owner-approved tests.
