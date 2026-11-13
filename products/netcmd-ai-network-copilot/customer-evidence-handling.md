# Customer Evidence Handling & Approval Guide

This guide is part of the NetCmd AI Network Copilot audit pack. It defines a safe, repeatable way to collect evidence for a customer-authorized network review.

## 1. Scope before collection

Record the customer, environment, review window, device families, approved collection method, and named customer approver. Confirm whether the engagement is read-only. Do not connect to a device or collect data until written authorization and scope are recorded.

## 2. Minimum evidence set

For each in-scope device, collect only what is needed to support the stated audit objective:

- Device inventory: hostname or customer-approved asset alias, vendor, model, software version, and site.
- Interface inventory: interface name, administrative/operational state, description, VLAN or role where relevant.
- Relevant configuration excerpts: only the sections needed to substantiate a finding.
- Supporting operational output: selected status, neighbor, routing, or security summaries relevant to the agreed scope.
- Collection metadata: collector, timestamp with timezone, source device alias, command or method, and tool version.

Do not collect full running configurations by default. Never collect passwords, private keys, API tokens, shared secrets, authentication databases, personal data, or unrelated customer records. If a command output includes a secret, stop, redact it locally, and record that redaction occurred without copying the secret.

## 3. Evidence integrity and storage

- Use customer-approved storage with access restricted to named project participants.
- Keep original evidence read-only; perform redaction and analysis on a separate working copy.
- Use stable evidence IDs such as `EV-001`, not customer usernames or personal identifiers.
- Record a SHA-256 checksum for each retained evidence file when the customer's tooling permits it.
- Do not upload customer evidence to public GitHub repositories, public issue trackers, or public AI prompts.
- Follow the customer's retention and deletion instructions; do not invent a retention period.

## 4. Finding format

Every finding must include:

1. Finding ID and concise title.
2. Affected asset alias and scope.
3. Observed fact, separated from interpretation.
4. Evidence IDs and collection timestamps.
5. Risk and business impact, with assumptions stated.
6. Recommended remediation and validation method.
7. Confidence level: high, medium, or low.
8. Customer owner and approval status.

Do not state that a control is absent solely because it was not visible in a partial configuration. Mark incomplete evidence as **Not verified** and request the missing approved evidence.

## 5. Change-control boundary

The audit pack is advisory and read-only. It must not push configuration, shut interfaces, change VLANs, rotate credentials, restart services, or modify customer systems. Any remediation is a separate change request that must include:

- Exact device and commands or configuration diff.
- Expected impact and outage risk.
- Backup and rollback procedure.
- Maintenance window and validation steps.
- Explicit approval from the customer's authorized change owner.

No approval means no change.

## 6. Customer handover checklist

- [ ] Scope and authorization recorded.
- [ ] Evidence inventory and timestamps included.
- [ ] Secrets and unnecessary personal data excluded.
- [ ] Each finding links to evidence IDs.
- [ ] Unknowns and partial coverage are clearly marked.
- [ ] Recommendations are separated from observed facts.
- [ ] Remediation is presented as a proposal, not as completed work.
- [ ] Customer has approved the report distribution list.

## 7. Report disclaimer

This is a bounded assessment based on the evidence supplied or collected within the approved scope and time window. It is not a guarantee that all vulnerabilities, misconfigurations, or operational risks have been identified. Customer approval, device access, and remediation remain under the customer's control.
