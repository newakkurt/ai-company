# AI Company — Combined Revenue Plan

**Decision date:** 2026-11-11  
**Target:** USD 5,000 gross monthly revenue  
**Starting budget:** USD 0  
**Initial offer:** Combined Network Audit + NetCmd + Network Automation

## Executive decision

Sell measurable network operations outcomes first. AI Company is the internal planning, analysis, QA and reporting layer; it is not marketed as an autonomous 13-agent company until durable workers, real provider calls and end-to-end tests prove that capability.

Keep every existing project and production service independent. This plan is documentation and a product backlog only; it does not change NetCmd, NetControl, paylasim-botu, or the current Render production service.

## Initial customer and pain

Target small and mid-sized IT teams, MSPs, hotels, schools, clinics, multi-branch retailers and local network integrators that operate Cisco, Huawei or Aruba switches but lack repeatable configuration reviews and monthly evidence.

Lead with these outcomes:
- Find risky or inconsistent switch configurations.
- Identify unused or undocumented access ports, VLAN/trunk mismatches and missing operational controls.
- Produce a readable, evidence-backed report with prioritized remediation suggestions.
- Turn repeatable checks into a monthly review and a safe change plan.

The first release is configuration-file based and read-only. No live-device access or configuration changes are included by default.

## Product bundle

### 1. Network Audit (core paid deliverable)
- Input: customer-supplied sanitized running configuration and optional inventory.
- Initial vendors: Huawei, Cisco, Aruba.
- Implemented first-pass checks: NTP, remote logging, AAA, Telnet-related directives and interface descriptions, all based only on supplied text evidence.
- Planned next checks (not yet implemented): SNMP posture, VLAN/trunk hygiene, unused-port candidates, port security, BPDU protections, DHCP snooping/DAI and vendor-specific management-plane checks.
- The current parser is a small first-pass module, not a complete compliance engine; every finding must retain source evidence and be human-reviewed.
- Output: executive summary, findings with evidence, severity, remediation commands as suggestions, exclusions/assumptions, and a PDF/CSV-ready report.
- Human review required before a report is delivered as a final assessment.

### 2. NetCmd (product-led acquisition and upsell)
- Keep the existing NetCmd repository and live site separate.
- Use its command catalogue, bilingual content and sample-output tools as a free discovery funnel.
- Paid value should be saved audit profiles, reusable report templates, bulk analysis, configuration diff and API access only after each feature is implemented and tested.
- Do not change the live NetCmd site or its payment setup as part of this branch.

### 3. Network Automation Service (higher-value add-on)
- Generate reviewed Python/Ansible plans for repeatable inventory, backup, compliance checks and monthly port reports.
- Start with dry-run and customer-approved read-only access.
- Change execution remains out of scope until there is per-action approval, backup, rollback plan and audit logging.

## Test pricing (not yet market-validated)

| Offer | Initial test price | Billing |
|---|---:|---|
| Single-site Network Audit | $149–$299 | One-time |
| Multi-site / larger estate Audit | $399–$799 | One-time |
| Monthly Network Health Review | $99–$299 | Monthly |
| Automation setup / first workflow | $299–$799 | One-time |
| Automation care and reporting | $199–$499 | Monthly |
| NetCmd Pro (when paid features exist) | $19/month | Monthly |

Quote by device count, number of sites, config quality and review effort. These are experiments, not a promise or a validated market benchmark. Taxes, payment processing and any customer-specific infrastructure are excluded.

## $5,000 monthly gross-revenue model

Illustrative target mix:
- 5 monthly Network Health Review customers × $299 = $1,495
- 5 Automation Care customers × $399 = $1,995
- 3 one-time Network Audit projects × $449 = $1,347
- 9 NetCmd Pro subscriptions × $19 = $171
- **Total = $5,008 gross/month**

This is a target composition, not a forecast or guarantee. It requires customer validation, delivery capacity and retention. Track gross revenue separately from fees, taxes, refunds and costs.

## Zero-budget operating rules

- Reuse the existing GitHub, Render Free and Supabase Free resources; do not create paid infrastructure or add a new paid provider.
- Respect free-tier limits. Render Free web services sleep after inactivity and do not provide a free always-on background worker; do not build a critical always-running queue around that assumption.
- Keep the current AI Company Render service stable. Any code work starts on a separate Git branch and is reviewed through a pull request.
- Keep NetCmd, NetControl and social bots in their own repositories and deployments.
- Never put API keys, customer configs or credentials in Git, logs, public issues or prompts.
- Ask customers to sanitize public IPs, usernames, secrets, SNMP communities and other sensitive values before upload.
- Do not promise autonomous device changes, automatic customer acquisition, or 24/7 worker execution.

## 30-day execution sequence

### Phase 0 — protect and validate (days 1–3)
1. Record production health and latest deploy before each release.
2. Verify real Gemini generation and Supabase write/read independently; readiness must not mean merely that an environment variable exists.
3. Correct the model name only after confirming a currently supported Google model ID.
4. Build a reproducible sample audit using synthetic/sanitized Cisco, Huawei and Aruba configurations.
5. Keep all production changes behind a reviewed PR.

### Phase 1 — sellable pilot (days 4–10)
1. Build a deterministic configuration parser and initial checks for the three vendors.
2. Generate one polished sample report with evidence and remediation suggestions.
3. Publish a concise English/Turkish offer page in a separate preview or PR; no changes to the current live NetCmd page without review.
4. Prepare a one-page scope, data handling statement and customer intake checklist.
5. Contact 30 qualified prospects manually; seek 3 pilot customers, not vanity traffic.

### Phase 2 — repeatability (days 11–20)
1. Turn repeated findings into versioned checks and tests.
2. Add report export and customer/site history only after access controls and retention are defined.
3. Offer monthly review and automation care to pilot customers.
4. Measure time per audit, findings per device, report acceptance and conversion.

### Phase 3 — recurring revenue (days 21–30)
1. Convert at least 2 pilot customers to a monthly plan if the value is proven.
2. Add only the NetCmd paid features that customers actually request.
3. Select a payment provider only after confirming country eligibility, fees and a no-upfront-cost path.
4. Review actual gross revenue, churn, delivery hours and support load against the $5,000 target.

## Success metrics

- 3 paid pilot customers.
- 1 reusable audit report template and automated tests for each supported vendor.
- 100% of findings traceable to configuration evidence or clearly marked assumptions.
- Zero production regressions in existing projects.
- First recurring revenue from at least 2 customers.
- Monthly gross revenue, average revenue per customer, conversion, retention and delivery hours tracked.

## Explicit non-goals for this phase

- Replacing or merging existing repositories.
- Enabling external actions or live switch changes.
- Claiming all 13 agents are autonomous workers.
- Purchasing domains, plans, APIs, hosting or advertising.
- Implementing subscriptions before there are working paid features and a verified payment path.

## Next engineering backlog

1. Expand the read-only vendor parser and normalized inventory model.
2. Implement and test the planned vendor-specific evidence checks (SNMP, VLAN/trunk, port security, STP/BPDU, DHCP snooping/DAI).
3. Deterministic HTML/Markdown report output and sample dataset.
4. Unit tests with sanitized sample configurations.
5. Customer-safe upload, deletion and retention workflow.
6. Pricing/landing page preview and pilot intake.
7. Production readiness work already tracked in GitHub issue #3 (Gemini, Supabase, durable queue and orchestration).
