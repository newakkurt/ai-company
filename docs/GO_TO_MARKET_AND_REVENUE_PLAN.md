# AI Company — Go-to-Market & Revenue Operating Plan
Status: Operating reference; payment configuration inspected in NetCmd-Site. Live payment acceptance still requires end-to-end verification.

## 1. Business objective
- Target: USD 5,000 monthly revenue (goal, not forecast or guarantee).
- Initial cash budget: USD 0.
- Initial offer: Combined — self-serve network audit tooling plus optional expert implementation/support.
- Primary commercial product: NetCmd. AI Company coordinates research, marketing, QA and finance reporting.
- Existing repositories and services are protected. AI Company may inspect NetCmd, NetControl and paylasim-botu read-only; no edits, deployments, database changes or customer-device changes without separate scoped owner approval.

## 2. Customer segments and acquisition
Target:
1. SMBs with 1–20 switches and no dedicated network automation team.
2. MSPs / system integrators managing multiple customer networks.
3. Huawei, Cisco and Aruba network administrators.
4. Network consultants needing repeatable audits and command references.

Acquisition channels:
- LinkedIn: relevant IT/network decision-makers; individually researched, consent-aware outreach.
- SEO: network audit, switch configuration audit, Huawei/Cisco/Aruba audit, unused-port review and network automation.
- YouTube: synthetic-data product demonstrations and technical explainers.
- Instagram: short verified demos and brand awareness.
- GitHub/community: useful free examples and sample reports; no spam.

Funnel: discovery/content → NetCmd landing page → safe demo/sample report → pilot or plan → clear scope/terms → verified payment → entitlement/onboarding → support/renewal.

Track source, campaign, consent, qualified lead, demo, proposal, payment state, activation, churn and support effort. Do not collect unnecessary personal data.

## 3. NetCmd payment setup — EXISTING CONFIGURATION FOUND
Source repository: https://github.com/newakkurt/NetCmd-Site
Source README: https://github.com/newakkurt/NetCmd-Site/blob/main/README.md
Public payment page configured in data/site.json: https://buymeacoffee.com/sevketkaynar

### A. Buy Me a Coffee — NetCmd PRO
- Existing public BMC page is configured as the support / membership destination.
- NetCmd's currently inspected README/config previously showed USD 22/month. Owner has now selected USD 69/month as the new target price for the AI-enhanced NetCmd PRO offer. This is a pricing decision, not yet a live checkout change.
- Customer must use the same email address for Buy Me a Coffee and their NetCmd account; the signed webhook maps supporter email to auth.users.
- Only the configured PRO membership level grants Premium. One-time coffee donations do NOT grant Premium.
- Expected webhook events: membership.started, membership.updated, membership.cancelled, membership.paused.
- Webhook signature header: x-signature-sha256; HMAC-SHA256 verification is implemented in supabase/functions/bmc-webhook.
- Required Supabase Edge Function secrets are named BMC_WEBHOOK_SECRET and BMC_PRO_MEMBERSHIP_LEVEL_ID. Supabase standard SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are used by the function.
- Webhook endpoint configured in NetCmd README: https://olbyrzqjdbxxsfaonsew.supabase.co/functions/v1/bmc-webhook
- Database migration: supabase/bmc_membership.sql. It uses event IDs for idempotency and only grants access for the configured membership-level ID.
- Deployment, live-mode event delivery, BMC membership-level ID and real payout settlement must be independently verified before describing the BMC path as fully live.
- Do not invent the BMC creator payout bank account or payout schedule. Those are private creator-dashboard settings and are not in the public repo.
- BMC platform and payment-processing fees must be included in net revenue reconciliation; verify current fee rates in the creator dashboard/provider terms rather than assuming a fixed rate.

### B. IBAN / bank transfer — SEMI-AUTOMATED ORDER FLOW EXISTS IN CODE
NetCmd README and supabase/iban_orders.sql describe:
1. Authenticated customer creates a 30-day or 365-day Premium order and receives an order code (NC-XXXXXX).
2. Customer transfers to the bank account displayed by NetCmd and puts the order code in the transfer description.
3. Customer clicks “Ödedim” / reports payment.
4. The system creates a pending premium request and sends an administrator notification to Telegram.
5. Human administrator checks the actual bank transaction and explicitly approves or rejects.
6. Approval enables Premium and marks the matching order paid; rejection marks it rejected.
- This is NOT automatic bank reconciliation. A customer pressing “Ödedim” is not proof of payment.
- Relevant migration: supabase/iban_orders.sql (README says run community.sql, ops2.sql, iban_orders.sql, waitlist.sql in that order).
- Render environment variable names used for the displayed bank details: BANK_IBAN (required), BANK_HOLDER (required), BANK_NAME (optional). Actual values are intentionally not in Git and must never be copied into AI prompts, source control, logs or agent memory.
- Display amount config: data/site.json uses premium_price_try; current public config has it blank. Therefore a fixed TRY amount is not currently recorded in that public config.
- Never infer or reveal the destination IBAN from the source repository. It must be managed only in the protected Render environment and verified by the owner.
- Admin approval remains a human control. Agents may reconcile read-only exports if explicitly provided, but cannot approve, reject, transfer or change payout details.

### C. Public seller and legal configuration gaps
- data/site.json has a seller display name, but address, tax office, tax number and phone are blank.
- contact_email is blank.
- premium_price_try is blank.
- Before public commercial scaling, owner must complete and verify seller/invoicing details, contact channel, local tax/accounting obligations, distance-sales and refund terms, privacy notice and support policy with qualified local advice.
- Do not claim legal or tax compliance from the presence of draft pages.

### D. Payment security and CFO reconciliation
- Keep bank account values, webhook secrets, service-role keys and payment credentials only in their intended protected provider/Render/Supabase secret stores.
- Never read, export, repeat, store or transmit secret values to AI Company agents. Share only safe metadata: provider, product, currency, amount, billing interval, event types, statuses, timestamps and masked references.
- Reconcile BMC gross receipts, fees, refunds, cancellations and net payouts against actual provider settlement records.
- Target price approved by owner: USD 69/month for AI-enhanced NetCmd PRO. The live BMC membership tier and NetCmd display config still require synchronized manual/provider-side update and verification. Until then, the live checkout remains unverified and must not be advertised as $69. Report the USD 5,000 goal as net collected revenue before tax/operating costs.
- Reconcile bank-transfer orders against the actual bank statement; only owner/admin confirmation changes an order to paid.
- Separate revenue earned, payment reported, payment confirmed, provider payout pending and bank settlement received.
- CFO must never initiate transfers, change payout bank details, issue refunds or spend money without explicit owner approval.

## 4. Pricing and product packaging — DECISION
The following is the single consistent commercial policy until real customer data justifies a reviewed change:
- Public self-serve product: AI-enhanced NetCmd PRO target price is USD 69/month recurring through the existing Buy Me a Coffee membership page. This is the owner's approved target price; it is NOT live until the BMC PRO membership tier is changed and tested, and NetCmd's displayed price is synchronized.
- Combined offer: NetCmd PRO at USD 69/month plus optional, supervised network audit / implementation assistance. Hands-on work is quoted individually after scope discovery; do not publish a made-up fixed service price or imply it is included free.
- Until checkout and site configuration are verified at USD 69, do not claim that customers can currently purchase at that price; keep the current checkout's actual price authoritative.
- One-time coffee support is a donation/support payment only and never activates PRO.
- Bank transfer remains a separate manual-verification path. No automatic entitlement until an owner/admin verifies the actual bank receipt and approves the order.
- Do not create extra public tiers or change prices until product limits, customer demand, support capacity, taxes and checkout behavior have been verified.

Revenue target definition: USD 5,000/month in net collected revenue after platform/payment fees, before tax and operating expenses. It is a target, not a forecast. At USD 69/month, using BMC's published fee examples (5% platform + 2.9% + USD 0.30 processing + 0.5% payout + possible 1% international + 0.5% subscription), an illustrative all-surcharges estimate is about USD 61.87 net per successful monthly payment; roughly 81 active monthly members would be needed to reach USD 5,000 from memberships alone. Actual net varies by payer country, card, currency, payout route and dashboard fee settings; CFO must use actual settlement records, not this estimate. See the official fee explanation: https://help.buymeacoffee.com/en/articles/8105744-how-to-calculate-charges-on-your-payment.

Other offers (USD 49/month Starter, USD 99/month Pro, USD 149+/month MSP, one-time guided audit USD 150–500) remain unvalidated hypotheses and must not be published as active offers. Before introducing further bundles, define supported vendors, device/site limits, report retention, support response, cancellation/refund terms and exclusions. Never promise unattended production changes.

## 5. Agent responsibilities
Current registry has 13 roles:
- CEO: priorities, approvals, revenue target review.
- Chief of Staff / PM: backlog, owners, dependencies and deadlines.
- Research: customer/competitor evidence and source links.
- Product & Business: packaging, interviews and pricing experiments.
- Marketing & Growth: SEO and acquisition experiments.
- Content: technical content, localization and demos.
- Software / Architect: isolated implementation plans and interface review.
- Network Engineer: technical accuracy and vendor scope.
- Data Analyst: funnel, MRR, churn, fee and cash-flow reporting.
- QA: test evidence and release gates.
- Security: privacy, secrets, access and threat review.
- Memory: approved decisions and lessons.

Gap and decision: create a dedicated 14th role named CFO / Finance & Revenue Operations. This is the approved target design, but it is NOT active until the agent registry, permissions and worker tests are changed and verified. Until then, Data Analyst prepares read-only finance summaries and CEO reviews them. CFO permissions must be read-only for provider/billing metadata and reports; no secrets, bank credentials, payout changes, refunds, transfers or spending authority.

## 6. Operating cadence (after worker/scheduler is implemented)
Daily:
- Research: qualified prospect and search-intent evidence.
- Marketing: one measurable acquisition experiment proposal.
- Content: one technical post/demo draft for human review.
- Data: authorized funnel and revenue snapshot.
- QA/Security: review public claims and release proposals.

Weekly:
- CEO chooses evidence-based experiments.
- PM tracks deliverables and blockers.
- Product reviews customer feedback and pilot outcomes.
- Finance reporting reconciles provider and bank records with owner-controlled approval.

No unsolicited bulk messaging, spam, login-protected scraping, fabricated testimonials or unverified claims.

## 7. Implementation gaps
P0:
- Verify the BMC membership tier, webhook deployment, secrets presence (without exposing values), test event and real paid/cancelled lifecycle.
- Verify Render BANK_IBAN/BANK_HOLDER/BANK_NAME are configured and that the displayed details match the owner's intended receiving account; never export their values.
- Set and verify premium_price_try if a fixed TRY amount is intended.
- Complete seller address/tax/phone/contact fields and legal/accounting review.
- Test the IBAN order → Telegram notification → human approval/rejection → Premium entitlement path end-to-end.
- Confirm Gemini provider readiness and real multi-agent end-to-end run.
- Implement persistent background worker/scheduler; a web panel alone does not make agents autonomous.
- Add task leases, retries/backoff, concurrency limits, usage limits, dead-letter handling and durable logs.

P1:
- Publish verified product scope, plan limits, terms, privacy, cancellation/refund and support pages.
- Create consent-aware CRM pipeline and lead capture.
- Measure visitor → lead → demo → paid → retained.
- Produce verified sample reports and onboarding docs.
- Run 5–10 customer discovery interviews and 2–3 supervised pilots.

P2:
- Customer workspaces, billing portal, usage metering and tenant isolation.
- Renewal/churn analysis and referral program.
- Dedicated Finance & Revenue Operations agent with read-only finance access and owner approval gates.

## 8. Safety and autonomy boundaries
Agents may research public information, draft content, analyze authorized metrics and create internal tasks. Human approval is mandatory before outreach is sent, content is published, production code is changed, a deployment is made, customer network configuration is changed, a refund is issued, money is transferred, payout details are changed or paid costs are incurred.

## 9. Success metrics
- Qualified leads/week
- Demo-to-paid conversion
- New paying customers/month
- MRR and one-time service revenue
- Gross margin after provider/API/support costs
- Refunds, disputes and churn
- Activation time and support hours/customer
- BMC net payouts and bank-transfer settlements reconciled separately

The USD 5,000 monthly target is a goal, not a forecast. Report pipeline, customer-reported payment, verified payment, provider payout and bank settlement as distinct states.
