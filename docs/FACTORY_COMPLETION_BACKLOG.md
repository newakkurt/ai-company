# New Akkurt AI Company — Factory Completion Backlog

This backlog defines measurable release gates. A checkbox is complete only when implementation, automated tests and a live verification record exist. A green GitHub Actions run alone is not proof of a live commercial workflow.

## P0 — Launch and first paid product

- [ ] Integrate and verify the autonomy/mail/sales feature branch in the production branch.
- [ ] Confirm the Render service has the required environment variables without exposing secret values.
- [ ] Verify live `/readyz`: 14 agents, provider ready, Supabase connected, worker enabled and running.
- [ ] Confirm the worker remains healthy across a service restart and resumes queued work without duplicate outputs.
- [ ] Add a durable, structured CRM for organizations, public business contacts, source URLs, consent/opt-out state, deduplication, outreach status and follow-up timestamps.
- [ ] Build a reviewed prospect-to-customer workflow: research -> evidence/fit score -> draft -> owner approval -> send -> reply tracking.
- [ ] Keep unsolicited bulk outreach disabled. Only send to lawful, appropriate business contacts under an approved policy; honour opt-outs and suppression lists.
- [ ] Build a product release pipeline: opportunity -> spec -> implementation -> tests -> security review -> package -> release notes -> sales page draft.
- [ ] Package NetCmd AI Network Copilot as a downloadable, versioned product with a working demo, sample data, setup guide, support policy and known limitations.
- [ ] Verify Buy Me a Coffee live product/tier, price, webhook signature, event deduplication, entitlement activation, cancellation and refund paths with a permitted test purchase.
- [ ] Verify the complete buyer journey from checkout to delivery/access; do not call a webhook notification a bank settlement.
- [ ] Publish seller identity, contact, privacy, refund/cancellation, tax/invoice and applicable consumer terms before paid promotion.
- [ ] Deliver an end-to-end first-customer pilot and record customer acceptance and payment evidence.

## P1 — Reliable company operations

- [ ] Move daily mail quotas and per-sender limits from process memory into durable storage.
- [ ] Add idempotency keys and retry/backoff for mail and payment event handlers.
- [ ] Add dead-letter queue, lease expiry, alerting and operator replay for failed tasks.
- [ ] Add backup/restore drill for task, CRM, product and payment records.
- [ ] Add provider cost/token telemetry, hard monthly budget caps and circuit breakers.
- [ ] Add product QA gates: unit tests, dependency audit, secret scan, package integrity and smoke tests.
- [ ] Add release artifact storage and checksums.
- [ ] Add revenue dashboard separating gross sales, fees, refunds, subscription status and verified bank settlement.
- [ ] Add owner dashboard for task queue, agent outputs, leads, campaigns, releases and incidents.

## P2 — Growth

- [ ] Add opt-in content scheduling and owner-approved publishing integrations.
- [ ] Add customer onboarding, support SLA tracking and renewal reminders.
- [ ] Add product usage analytics with privacy-preserving aggregation.
- [ ] Add multilingual product pages and SEO quality checks.
- [ ] Add customer feedback loop and monthly product roadmap ranking.

## Non-negotiable safety boundaries

- No secret, password, API key, private key, SNMP credential or bank detail in prompts, logs, reports or Git.
- No device access or production configuration changes without explicit customer authorization and a separate approved change plan.
- No payment, paid API usage, advertising spend, refunds, legal commitments or public statements outside configured limits and owner-approved policy.
- AI-generated prospects, claims and product outputs must be evidence-checked before customer contact.
- The system must never invent revenue, customer commitments, compliance status or bank settlement.
- Keep an audit record for every approval, outbound message, payment event and release.


## Digital product factory implementation note (2026-11-12)

The first bounded factory implementation is exposed at `/api/factory/*`:
- Research tasks are queued for the research, product, marketing, architecture, network, security and QA roles.
- Opportunity scoring uses explicit weighted criteria and a security-risk penalty.
- MVP generation supports Python API, static web app and Python CLI package types.
- The release bundle includes source, README, product spec, sample data, test plan, QA/security report, changelog, manifest, SHA-256 and a backup ZIP copy.
- Generated source is never executed by the factory; runtime tests remain unverified and every release requires human review.
- The current Render Free filesystem is ephemeral. Durable release delivery remains gated on persistent object storage being configured.


## Zero-budget worker scheduling (2026-11-12)

- Routine work is rotated across the seven days instead of seeding every marketing and research playbook on every day.
- The normal daily workload is capped at one daily focus plus one weekly workstream; the global prospect scan is an every-other-week addition.
- Routine tasks use CEO + two specialists. The product factory uses CEO + four specialists.
- Provider quota exhaustion (HTTP 429 / RESOURCE_EXHAUSTED) is not retried every 30 minutes. It waits at least 24 hours and gets one bounded retry.
- This reduces unnecessary free-tier requests. It does not create additional provider quota; the Groq fallback still requires its own configured key.
