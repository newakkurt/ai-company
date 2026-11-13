# NetCmd AI Network Copilot — Sample Audit Report

> **Demonstration data only.** All device names, IP addresses, observations and timestamps below are fictional lab examples. This is not a report about a real customer network and must not be presented as one.

## Executive summary

- Customer/site: DEMO-LAB / Istanbul (fictional)
- Audit date: 2026-11-11
- Authorized scope: Fictional read-only demonstration of three switches
- Devices reviewed: 3 (Huawei, Cisco, Aruba)
- Evidence collection method: Manually prepared illustrative CLI excerpts; no device was contacted
- Overall posture: **Not assessed** — sample data is insufficient for a real security rating
- Limitations: No production configuration, authentication, routing, wireless, firewall, or physical-layer evidence was collected

## Inventory summary

| Vendor | Device alias | Model / OS (illustrative) | Management IP (documentation-only) |
|---|---|---|---|
| Huawei | LAB-HW-01 | S57xx / VRP (example) | 192.0.2.11 |
| Cisco | LAB-CS-01 | Catalyst / IOS XE (example) | 192.0.2.12 |
| Aruba | LAB-AR-01 | ArubaOS-Switch (example) | 192.0.2.13 |

The addresses use TEST-NET-1 documentation space and are not customer endpoints.

## Findings

| ID | Device/interface | Severity | Evidence | Observation | Recommendation | Status |
|---|---|---|---|---|---|---|
| DEMO-001 | LAB-HW-01 / GE1/0/8 | Informational | DEMO-EV-001 | Example access port has no description in the fictional output | Confirm business owner and document the port purpose before any change | Not verified |
| DEMO-002 | LAB-CS-01 / Gi1/0/12 | Low (illustrative) | DEMO-EV-002 | Example interface is administratively down | Confirm whether the shutdown is intentional; do not enable automatically | Not verified |
| DEMO-003 | LAB-AR-01 / VLAN 20 | Informational | DEMO-EV-003 | Example inventory indicates a user VLAN | Validate VLAN purpose and approved segmentation policy with the customer | Not verified |

Severity labels are illustrative only. They are not a production risk assessment.

## Evidence register

| Evidence ID | Source | Collection time | Content |
|---|---|---|---|
| DEMO-EV-001 | Fictional Huawei CLI excerpt | 2026-11-11 10:00 +03:00 | Example interface brief and description output |
| DEMO-EV-002 | Fictional Cisco CLI excerpt | 2026-11-11 10:05 +03:00 | Example interface status output |
| DEMO-EV-003 | Fictional Aruba CLI excerpt | 2026-11-11 10:10 +03:00 | Example VLAN summary |

No secrets, customer records, or real device outputs are included.

## Prioritized action plan

1. Confirm the intended purpose and owner of any undocumented interface.
2. Confirm whether administratively down interfaces are intentionally disabled.
3. Compare VLAN usage with the customer's approved network design.
4. Request additional authorized evidence before assigning a security posture or making stronger claims.

## Change-control boundary

This sample is read-only. It does not authorize configuration changes, device access, port shutdown/enablement, VLAN changes, or remediation. Any customer remediation requires a separate written change request and approval from the customer's authorized owner.

## Demo handover

- [x] Clearly labelled fictional demonstration
- [x] No real customer data or credentials
- [x] Evidence IDs and timestamps included
- [x] Unverified observations labelled
- [x] No automatic changes proposed or executed
