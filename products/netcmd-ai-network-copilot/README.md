# NetCmd AI Network Copilot — Network Audit Starter Pack

Version: 0.2.0 (first executable product candidate)  
Product owner: New Akkurt AI Company  
Primary audience: SMB IT teams, MSPs, and Huawei/Cisco/Aruba network administrators.

## What the buyer receives
- A vendor-neutral network discovery and audit checklist.
- A port inventory CSV template.
- A read-only evidence collection guide.
- A risk-ranked findings and remediation report template.
- A customer handover checklist.
- An offline configuration evidence checker for sanitized Cisco, Huawei and Aruba text exports.
- Synthetic sample data and a repeatable test command.

## Run the included tool
The first executable component is in tools/. It uses only Python's standard library and works offline:

```bash
cd tools
python audit_config.py sample-cisco-config.txt --vendor auto --output sample-report.md
python -m unittest -v
```

The checker reports EVIDENCED, NOT_EVIDENCED, REVIEW or UNKNOWN. A missing match is not proof that a control is absent. The report does not reproduce raw configuration lines, credentials or secrets. Review the tool README for limitations.

## Intended value
Help a small IT team turn switch inventory and configuration evidence into a repeatable, documented network health review. The starter pack does not connect to customer devices, change configurations, or replace a qualified network engineer.

## Product scope
Supported vendor families for the workflow: Huawei VRP, Cisco IOS/IOS-XE, and ArubaOS-Switch/AOS-CX. Exact commands vary by model and software release; verify commands against the vendor's documentation before use.

## Quick start
1. Obtain written authorization and define device/site scope.
2. Export inventory and read-only command output using the customer's approved process.
3. Fill templates/port-inventory.csv.
4. Run the offline checker against sanitized configuration text.
5. Record evidence and findings using templates/audit-report.md.
6. Prioritize issues by impact, likelihood, and exposure.
7. Review remediation with the customer's network owner; do not apply changes without a separate change approval.

## Commercial packaging
The intended combined offer is NetCmd PRO plus optional supervised audit/implementation assistance. The owner's target price for AI-enhanced NetCmd PRO is USD 69/month, but do not advertise that as a live checkout price until the Buy Me a Coffee membership tier and entitlement webhook have been tested end-to-end.

Checkout/support page: https://buymeacoffee.com/sevketkaynar

## Safety and limitations
- Read-only discovery and reporting only.
- Never paste credentials, API keys, private customer data, or bank details into this pack or AI prompts.
- Do not scan networks without written authorization.
- No automatic production configuration changes.
- Sample data is synthetic and clearly labelled.
- The checker is a lightweight evidence indicator, not a compliance certification, security guarantee or replacement for vendor documentation.
- Seller identity, tax/invoice details, contact address, terms, privacy, refunds and checkout need owner/provider verification before broad paid promotion.
