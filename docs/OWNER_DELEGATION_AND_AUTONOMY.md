# AI Company — Owner Delegation & Autonomous Operating Mandate

Status: Owner-approved operating target. This document is a policy and implementation specification; it does not mean the background worker, sales integrations, product builder, or autonomous sales execution are already deployed.

## Owner's role
The owner wants to monitor verified revenue and bank settlements, not manage daily task assignment. AI Company should independently discover opportunities, build and test products, find qualified customers, prepare sales material, and operate a measurable revenue pipeline.

## Company objective
- Net collected revenue target: USD 5,000/month (goal, not a forecast).
- Initial operating cash budget: USD 0; prefer free tiers and no paid ads or paid APIs without explicit approval.
- Primary product line: AI-assisted network operations and network audit tools, starting with NetCmd.
- Owner-approved target price for AI-enhanced NetCmd PRO: USD 69/month. This is not a live checkout price until BMC membership tier, NetCmd price display, webhook entitlement, and a real test transaction are verified together.
- Existing BMC page: https://buymeacoffee.com/sevketkaynar

## Autonomous work the agents should perform
1. Continuously research customer problems, competitors, search demand, and product opportunities using public sources.
2. Rank product ideas by customer value, feasibility, differentiation, support burden, security risk, and time to first revenue.
3. Select a small number of product bets; do not create many unfinished products.
4. Write specifications, implement code in isolated feature branches, add tests, run security and QA checks, and open reviewable pull requests.
5. Maintain demos, sample data, documentation, onboarding, pricing experiments, and release notes.
6. Identify qualified prospects from public business information; maintain a deduplicated CRM with evidence, fit rationale, source URL, and next step.
7. Prepare personalized sales proposals and outreach drafts; track funnel stages from lead to demo, proposal, verified payment, activation, and renewal.
8. Create useful technical content and campaign drafts; measure visits, leads, conversions, MRR, churn, support effort, and net settlements.
9. Report only evidence-backed results. Never fabricate leads, customers, product capabilities, testimonials, payments, or revenue.

## Role ownership
- CEO: strategy, prioritization, risk and weekly performance.
- Chief of Staff / PM: task breakdown, dependency management, deadlines and blockers.
- Research: market evidence, competitor analysis and qualified prospect discovery.
- Product & Business: product selection, customer problem validation, packaging and pricing proposals.
- Software / Architect: architecture, implementation plans and code review.
- Network Engineer: vendor accuracy and network-domain product features.
- Marketing & Growth: SEO, channel strategy, funnel experiments and campaign measurement.
- Content: technical tutorials, demos, landing-page copy and localization.
- Data Analyst: product analytics, funnel metrics and revenue dashboards.
- QA: automated tests, regression tests and release gates.
- Security: threat modeling, secret handling, privacy and access control.
- Memory: durable approved decisions, customer feedback and lessons.
- CFO / Finance & Revenue Operations: proposed 14th role; must be added to the registry and tested before being described as active. Until then Data Analyst prepares read-only finance summaries and CEO reviews them.

## Permissions and safety boundaries
### May run autonomously once implemented
- Public web research and analysis.
- Product specifications, code generation and tests in isolated branches.
- Internal backlog, CRM records from public business data, reports and draft content.
- Synthetic-data demos and sample reports.
- Read-only revenue/funnel analysis using authorized, non-secret data.
- Automated entitlement updates from verified provider webhooks.

### Must remain protected
- Never expose or copy bank account numbers, webhook secrets, API keys, service-role keys, passwords, or private customer data into prompts, logs, Git, reports, or agent memory.
- Never mark a bank transfer paid based only on a customer clicking “paid”; owner/admin must verify the bank receipt.
- Never initiate bank transfers, change payout details, issue refunds, spend money, buy ads, sign contracts, or make legal/tax representations.
- Never send bulk unsolicited messages, spam, deceptive claims, or scrape login-protected sources. Outbound contact must use lawful, consent-aware channels, clear sender identity, opt-out handling, and configured rate limits. Until a compliant sending integration and permission controls are implemented, agents prepare drafts but do not send.
- Do not modify or deploy to existing NetCmd, NetControl, or paylasim-botu production systems without a separately scoped release authorization. Build and test new products in isolated resources.
- Product releases must have passing tests, security review, rollback plan, and auditable release record. Production changes to protected existing projects require owner approval.

## Required infrastructure before claiming autonomy
- Persistent hosted worker/scheduler; FastAPI in-process background tasks are not a durable queue.
- Durable task queue with leases, retries, backoff, idempotency, dead-letter handling, concurrency limits, and task history.
- Agent tool permissions and sandboxed repository workspaces.
- Git branch/PR workflow with CI tests and security checks.
- CRM/lead store with deduplication, source evidence, consent/legal basis, opt-out and retention controls.
- Approved content publishing and compliant sales integrations, each with scoped credentials and audit logs.
- Verified payment webhooks, subscription lifecycle tests, and reconciliation reports.
- Budget guardrails that hard-stop paid usage at USD 0 unless the owner explicitly authorizes a budget.

## Operating rhythm
- Daily: market scan, prospect discovery, product build/test queue, funnel/payment reconciliation, blockers and concise owner report.
- Weekly: choose one highest-value product/revenue experiment, review conversion and retention, close stale tasks, and report net collected revenue separately from reported or pending payments.
- Monthly: review pricing, churn, gross margin, support load, tax/accounting obligations and whether the USD 5,000 target is becoming more or less achievable.

## Truthful status rule
A role in config is not proof of an active agent. A planned task is not completed work. A running web process is not a persistent worker. A drafted message is not a sale. A customer-reported payment is not verified revenue. A successful deployment is not proof of customer value. Report each state separately and cite test/deploy evidence.
