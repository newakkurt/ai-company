# Network Audit Checklist

Use only with written customer authorization. Record evidence, not assumptions.

## 1. Scope and ownership
- [ ] Customer/site and business owner recorded.
- [ ] Authorized subnets, devices, and maintenance window recorded.
- [ ] Read-only access method approved.
- [ ] Emergency contact and escalation path confirmed.
- [ ] Data retention and deletion date agreed.

## 2. Inventory and topology
- [ ] Vendor, model, software version, hostname, serial reference and management IP recorded.
- [ ] Device role and site/rack/closet recorded.
- [ ] Uplink/downlink relationships documented.
- [ ] VLANs, trunks, LAGs and routed interfaces inventoried.
- [ ] Firmware lifecycle and support status checked against vendor sources.

## 3. Layer 2 health
- [ ] Access/trunk mode matches the documented design.
- [ ] Native VLAN and allowed VLAN lists reviewed.
- [ ] STP root and topology changes reviewed.
- [ ] Loop protection / BPDU guard policy reviewed where supported.
- [ ] Unused ports identified and owner-confirmed.
- [ ] Port descriptions and patch-panel references reviewed.
- [ ] Link errors, discards, flaps and speed/duplex mismatches reviewed.

## 4. Layer 3 and services
- [ ] Default gateways and routing adjacencies documented.
- [ ] DHCP relay/snooping and address scope ownership reviewed.
- [ ] DNS/NTP sources and reachability checked.
- [ ] ACLs and management-plane exposure reviewed.
- [ ] Redundancy and failover behavior documented.

## 5. Security posture
- [ ] Named admin accounts and AAA/RADIUS/TACACS+ status reviewed.
- [ ] SSH and secure management protocols preferred.
- [ ] SNMPv3 preferred; community strings are not copied into reports.
- [ ] Management access restricted to approved sources.
- [ ] Port security / 802.1X policy reviewed where appropriate.
- [ ] Configuration backup process and restore test evidence recorded.
- [ ] Logging, time synchronization and alert delivery reviewed.

## 6. Evidence and report
- [ ] Each finding has device, evidence, impact, likelihood and recommendation.
- [ ] Severity is justified and reproducible.
- [ ] Vendor/model/software applicability is stated.
- [ ] Remediation is separated from observation.
- [ ] Customer owner approves any change plan separately.
- [ ] Report is reviewed for secrets and personal data before delivery.

## Severity guide
- Critical: active compromise, outage, or immediate broad exposure supported by evidence.
- High: material security or availability weakness with a credible attack/failure path.
- Medium: meaningful control gap or operational risk with limited scope.
- Low: hygiene, documentation, or maintainability improvement.
- Informational: observation without demonstrated risk.
