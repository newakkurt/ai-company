# AI Company — Go-to-Market & Revenue Operating Plan
Status: Draft operating plan (not a live payment integration)

## 1. Business objective
- Target: USD 5,000 monthly revenue.
- Initial cash budget: USD 0.
- First commercial offer: Combined — self-serve network audit tooling plus optional expert implementation/support.
- Primary product asset: NetCmd. AI Company is the internal planning, research, marketing, QA and reporting layer.
- Protect existing repositories and services. AI Company may inspect them read-only; it must not modify NetCmd, NetControl, paylasim-botu or their databases without a separately scoped approval.

## 2. Initial customer segments
1. Small and mid-sized businesses with 1–20 network switches and no dedicated network automation team.
2. Managed service providers / system integrators managing multiple customer networks.
3. IT/network administrators responsible for Huawei, Cisco and Aruba estates.
4. Network consultants who need repeatable audit reports and command references.

Do not claim support for a vendor, feature or security control until QA verifies it.

## 3. Offers and pricing hypotheses
These are experiments, not published commitments:
- Free: public command library, sample reports and a limited sample audit workflow.
- Network Audit Starter: test price USD 49/month.
- Network Audit Pro: test price USD 99/month.
- Multi-site / MSP: test price USD 149/month and upward only after validating usage and support costs.
- One-time guided audit / implementation: test range USD 150–500, scoped per engagement.

Before publishing prices, define limits, supported vendors, number of devices/sites, report retention, support response, cancellation/refund terms and what is explicitly excluded. Never promise unattended production changes in the initial offer.

## 4. Customer acquisition funnel
Discovery:
- LinkedIn: useful technical posts and direct, individually researched outreach to relevant IT/network decision-makers.
- SEO: focused pages for network audit, switch configuration audit, Huawei/Cisco/Aruba audit, unused-port review and network automation.
- YouTube: short demonstrations using synthetic/sample configurations; never expose customer configs or secrets.
- Existing social channels: repurpose verified demos to Instagram and YouTube; prioritize LinkedIn for B2B.
- GitHub/community: publish genuinely useful free examples and sample reports; no spam.

Conversion:
1. Visitor lands on a focused NetCmd page.
2. Visitor sees supported-vendor scope, screenshots/sample output and clear limitations.
3. Visitor runs a safe sample/demo with synthetic data.
4. Visitor requests a pilot or selects a plan.
5. Customer receives a written scope, terms and invoice/payment instructions.
6. Payment is confirmed by provider/webhook or manually reconciled before access is granted.
7. Onboarding, first report, support and renewal reminders follow.

Track source, campaign, landing page, lead consent, qualification, demo, proposal, payment status, activation, churn reason and support effort. Do not collect unnecessary personal data.

## 5. Payment and settlement — NOT CONFIGURED
No destination IBAN or payment provider is currently confirmed in this repository. Do not invent or hardcode an IBAN.
Required before accepting money:
- Confirm the legal seller / invoicing entity and country.
- Select a payment provider that supports that seller, the desired currencies, subscriptions and international cards.
- Complete provider KYC and business verification.
- Add the seller's verified bank account in the provider dashboard. Provider settlement goes to that bank account under its payout schedule and fees; the provider, not an AI agent, handles card data.
- Configure signed webhook verification, idempotency, payment/refund/dispute states and reconciliation.
- Grant product access only after a verified paid event or an explicitly recorded manual payment check.
- Keep tax, invoicing, consumer rights, privacy and refund requirements under qualified local review.

CFO/finance workflow:
- Record gross payment, currency, provider fee, refund/chargeback, net settlement, payout date and invoice reference.
- Reconcile provider transactions against bank settlements.
- Produce daily exceptions and monthly profit/loss and cash-flow summaries.
- Never initiate transfers, change payout bank details, issue refunds or spend money without the owner's explicit approval.
- Never put IBANs, bank credentials, API secrets or customer payment data in prompts, Git, logs or agent memory.

## 6. Agent responsibilities
Current 13-role registry:
- CEO: weekly priorities, approval queue and revenue target review.
- Chief of Staff / PM: backlog, owners, dependencies and deadlines.
- Research: customer/competitor evidence and source links.
- Product & Business: offer design, packaging, customer interviews and pricing experiments.
- Marketing & Growth: SEO, acquisition experiments and funnel metrics.
- Content: publish-ready technical content, localization and demo scripts.
- Software / Architect: propose isolated implementation plans and review interfaces.
- Network Engineer: technical accuracy and supported-vendor scope.
- Data Analyst: funnel, conversion, MRR, churn and cohort reporting.
- QA: test evidence and release gates.
- Security: privacy, secrets, access and threat review.
- Memory: approved decisions and experiment outcomes.

Gap: there is no dedicated CFO/Finance Agent in the current 13-role registry. A 14th Finance & Revenue Operations role is recommended, but is not yet implemented. Until then, assign finance analysis to Data Analyst with CEO review; do not claim an independent CFO is active.

## 7. Operating cadence (target once worker is implemented)
Daily:
- Research: collect qualified prospect and search-intent evidence.
- Marketing: propose one measurable acquisition experiment.
- Content: prepare one useful technical post or demo asset for human review.
- Data: update funnel and revenue metrics from connected, authorized sources.
- QA/Security: review any proposed public claim or release.

Weekly:
- CEO selects experiments based on evidence.
- PM tracks deliverables and blockers.
- Product reviews customer feedback and pilot outcomes.
- CFO role (when implemented) reconciles payments and cash flow.

No unsolicited bulk messaging, spam, scraping behind logins, fabricated testimonials, unverified claims or autonomous financial transactions.

## 8. Current implementation gaps
P0 — blockers:
- Confirm seller/legal entity and country-specific ability to sell and invoice.
- Choose a supported payment provider and verify its payout/settlement support for the seller.
- Add verified payout bank account in provider dashboard; IBAN intentionally absent from Git.
- Implement checkout/payment status, signed webhooks, idempotency, refunds and access entitlements.
- Confirm Gemini provider readiness and run a real multi-agent end-to-end test.
- Implement a persistent background worker and scheduler. A web panel alone does not make agents autonomous.
- Add agent task leases, retry/backoff, concurrency limits, budget/token limits, dead-letter handling and durable logs.

P1 — revenue readiness:
- Publish product scope, plans, terms, privacy, cancellation/refund and support pages.
- Create a lead/CRM pipeline and consent-aware contact process.
- Instrument analytics for visitor → lead → demo → paid → retained.
- Produce verified sample audit reports and onboarding docs.
- Run 5–10 customer discovery interviews and 2–3 supervised pilots before scaling.

P2 — scale:
- Add customer workspace, billing portal, usage metering and tenant isolation.
- Add monthly reporting, renewal/churn analysis and referral program.
- Add finance role only with scoped access and owner approval gates.

## 9. Safety and autonomy boundaries
Autonomous agents may research public information, draft content, analyze approved metrics and create internal tasks. Human approval is required before sending outreach, publishing content, changing production code, deploying, changing customer configuration, issuing refunds, transferring funds, changing payout details or incurring paid costs.

## 10. Success metrics
- Qualified leads / week
- Demo-to-paid conversion
- New paying customers / month
- Monthly recurring revenue (MRR)
- One-time service revenue
- Gross margin after provider/API/support costs
- Activation time and first-value completion
- Churn, refunds and support hours per customer

The USD 5,000 target is a goal, not a forecast or guarantee. Report actual collected and settled revenue separately from pipeline, proposals and unpaid invoices.
