# Roadmap and production gates

Status snapshot: 2026-11-12. Items described as "feature branch" are implemented and tested in branches but are not live until the PR stack is merged and the Render service is deployed.

## Implemented / validated in feature branches

- [x] 14-role registry, bounded routing and analysis-only task runner.
- [x] Gemini primary / Groq fallback provider adapter.
- [x] Idempotent daily/weekly scheduler with bounded work and quota-aware retry delays.
- [x] Supabase RLS and server-side API gate for hosted state.
- [x] One-time scoped approval engine with API and Telegram decision support.
- [x] Durable product release storage, ZIP checksum verification and listing/download API.
- [x] Product publication requires owner approval bound to product ID + SHA-256.
- [x] CRM source validation with DNS/IP pinning, redirect revalidation and public HTTPS-only fetching.
- [x] CRM sales stages and proposal drafts require human verification.
- [x] Mail auto-reply requires trusted Authentication-Results with DMARC pass and SPF or DKIM pass.
- [x] Persistent idempotent mail send reservations and daily/sender caps.
- [x] BMC payment event ledger, product entitlement, revocable download token and transactional email delivery path.
- [x] Task heartbeat prevents long model calls from being requeued solely because updated_at went stale.
- [x] Unit tests on Python 3.10, 3.11 and 3.12.

## Required before calling the company operational

1. [ ] Merge the tested PR stack in dependency order and deploy to Render with explicit owner approval.
2. [ ] Confirm one active worker consumer; configure GitHub Actions secrets or intentionally enable the embedded Render worker, not both by accident.
3. [ ] Add GitHub Actions secrets: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_DB_GATE_KEY`, and at least one of `GEMINI_API_KEY` / `GROQ_API_KEY`.
4. [ ] Verify Render environment: `AI_COMPANY_API_KEY`, Supabase credentials, model key, Telegram settings and correct public URL.
5. [ ] Configure each BMC level ID in `BMC_PRODUCT_LEVEL_MAP` with a real published `product_id` and exact USD price.
6. [ ] Configure a dedicated SMTP mailbox and test transactional delivery; keep auto-reply in draft mode until authentication headers are verified.
7. [ ] Generate one real product release, inspect its contents, run it in an isolated QA sandbox, approve it, and publish it.
8. [ ] Run a controlled end-to-end purchase, verify webhook idempotency, email delivery, download expiry/count, cancellation and refund revocation.
9. [ ] Verify lead sources and manually approve at least one CRM company before any proposal workflow.
10. [ ] Complete KVKK / ETK / GDPR and tax/accounting review before any outbound campaign or commercial operation.

## Remaining engineering work

- [ ] True isolated runtime QA for generated ZIPs (network disabled, resource limits, dependency/security scan).
- [ ] CRM owner review UI for source evidence, contact legal basis, suppression and follow-up.
- [ ] Permission-based outreach workflow with one-to-one human approval, bounce/opt-out handling and provider reputation monitoring.
- [ ] Sales dashboard: qualified leads, proposals, payment events, refunds, entitlements and bank settlements.
- [ ] Product version upgrade / license lifecycle and buyer self-service.
- [ ] Durable backup and restore rehearsal for Supabase and artifacts.
- [ ] Production monitoring, dead-letter review UI and alert thresholds.
- [ ] Invoice, VAT, accounting and payout-to-bank reconciliation process.

## Verified current database snapshot

At the last read-only inspection:
- 16 CRM company records existed; their source-validation status was `not_checked` before the new verifier was deployed.
- 0 product releases were stored.
- 0 product entitlements and 0 payment ledger entries were present.
- No paid customer journey had been proven end-to-end.

These numbers must be refreshed after deployment and live tests. A passing unit test is not proof of a live sale.
