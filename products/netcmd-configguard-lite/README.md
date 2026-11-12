# NetCmd ConfigGuard Lite 1.0.0

Offline, read-only configuration baseline auditor for Cisco IOS, Huawei VRP and ArubaOS-Switch text snapshots.

## Requirements
- Python 3.10+
- Standard library only; no pip dependencies

## Run

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m netcmd_configguard.audit examples/huawei-sample.cfg --vendor huawei
PYTHONPATH=src python -m netcmd_configguard.audit examples/cisco-sample.cfg --format json --output report.json
```

## Features
- 10 baseline markers per vendor: SSH, AAA, NTP, logging, SNMPv3, HTTP management, BPDU protection, DHCP snooping, port security and trunk VLAN restrictions.
- Markdown and JSON reports with severity and remediation notes.
- Automatic vendor detection fails closed when syntax is ambiguous.

## Safety
No network access, SSH, SNMP, API calls, device discovery, configuration changes or credential collection. A matching line is only a text marker, not proof of operational state, correct scope or secure parameter values. Review device model, OS release, interface context and topology before applying any remediation. This is a starter baseline, not a compliance certification.

## License
MIT.
