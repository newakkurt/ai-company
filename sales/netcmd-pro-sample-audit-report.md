# NetCmd PRO — Illustrative Network Audit Report

**Document type:** sales demo mock-up  
**Data classification:** entirely fictional / synthetic  
**Status:** illustrative layout only; not produced by a live NetCmd PRO production analysis  
**Scope:** one fictional office site, two switches, one firewall; read-only evidence supplied by an authorized operator

## Executive summary

This sample demonstrates how a small network review could present evidence, risk, and next actions in one concise report. It does not claim that the product has completed a customer audit or that any finding exists on a real network.

| Area | Illustrative result | Priority |
|---|---|---|
| Management access | Telnet shown as enabled on a fictional switch | High |
| Time synchronization | NTP server not shown in the supplied fictional excerpt | Medium |
| Access-port hygiene | Two unused ports shown as administratively up | Medium |
| Evidence quality | One device excerpt is incomplete | Review |

## Findings

### F-01 — Insecure management protocol appears enabled
- **Severity:** High
- **Synthetic evidence:** `line vty 0 4` / `transport input telnet ssh`
- **Why it matters:** Telnet does not protect management credentials and session content with encryption.
- **Suggested action:** Confirm the device's management-plane policy; disable Telnet where operationally approved and retain SSH with approved authentication controls.
- **Validation:** Re-check the running configuration and confirm authorized management access still works.

### F-02 — Time source is not evidenced
- **Severity:** Medium
- **Synthetic evidence:** No NTP configuration appears in the provided excerpt; this is not proof that NTP is absent from the device.
- **Why it matters:** Consistent time supports event correlation and incident investigation.
- **Suggested action:** Verify the full configuration and approved NTP design before making changes.
- **Validation:** Confirm synchronized time and expected NTP peer status.

### F-03 — Potentially unused access ports require owner confirmation
- **Severity:** Medium
- **Synthetic evidence:** Fictional inventory lists ports Gi1/0/17 and Gi1/0/18 as link-down with no description.
- **Why it matters:** Unused active ports can increase the available attack surface.
- **Suggested action:** Check cabling, endpoint ownership, and change records; only then apply the organization's approved shutdown policy.
- **Validation:** Record owner approval and verify the resulting interface state.

## Recommended action plan

1. Validate the completeness and provenance of all supplied evidence.
2. Confirm each finding with the device owner; do not treat missing excerpt text as proof of missing configuration.
3. Agree on a maintenance window and rollback plan before any change.
4. Apply approved changes through the customer's normal change-control process.
5. Re-collect read-only evidence and close findings only after verification.

## Boundaries

- This is a fictional demonstration document, not a real customer report, security certification, compliance attestation, or guarantee.
- No device was contacted; no credentials, customer configurations, or personal data were used.
- NetCmd PRO is not represented as performing any action that has not been verified in a real pilot.
- No configuration changes are recommended without customer authorization and change control.
