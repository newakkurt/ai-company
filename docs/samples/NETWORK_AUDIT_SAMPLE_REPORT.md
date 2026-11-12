# Network Configuration Audit — Sanitized Sample

- Vendor: Cisco
- Findings: 3
- Mode: Read-only text analysis

> This sample is generated from a synthetic configuration. It is not a live-device assessment or compliance certification.

## Findings

### 1. [HIGH] Telnet management directive found
- Check: management.telnet
- Evidence: transport input telnet ssh
- Recommendation: Verify exposure and migrate to SSH through an approved change; do not remove access without a tested recovery path.

### 2. [MEDIUM] SNMP community string directive found
- Check: management.snmp_community
- Evidence: snmp-server community [REDACTED] ro
- Recommendation: Prefer SNMPv3 authPriv, restrict manager source addresses, and rotate any exposed community string.

### 3. [LOW] Physical interfaces without descriptions found
- Check: interfaces.missing_description
- Evidence: interface GigabitEthernet1/0/2
- Recommendation: Confirm the port's owner and purpose, then document it; do not infer an undocumented port is unused.

## Scope and limitations

- Analysis is limited to supplied text; sanitized, partial, or truncated configs can create false positives and false negatives.
- No device connection, command execution, configuration change, credential validation, or shutdown action is performed.
- Credential-like values are redacted from report evidence. The original configuration is not stored by this module.
- Reachability, effective policy, hardware state, software version, and runtime behavior cannot be established from a text file alone.
- Review every finding with the network owner before making changes.
