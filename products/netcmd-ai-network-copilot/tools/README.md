# NetCmd Offline Configuration Evidence Checker

A small, read-only starter utility included with the NetCmd AI Network Copilot launch pack.

## Requirements
- Python 3.10+
- No third-party packages
- Sanitized text exports only

## Run
From this directory:

```bash
python audit_config.py sample-cisco-config.txt --vendor auto --output sample-report.md
```

Or specify a vendor:

```bash
python audit_config.py sanitized-switch.txt --vendor huawei
python audit_config.py sanitized-switch.txt --vendor aruba
```

## Test
```bash
python -m unittest -v
```

## Status meanings
- `EVIDENCED`: at least one recognized configuration indicator was found.
- `NOT_EVIDENCED`: this export did not contain a recognized indicator. This is not proof that the control is absent.
- `REVIEW`: a recognized exception/disable indicator or manual review condition was found.
- `UNKNOWN`: vendor family could not be identified.

The tool deliberately avoids copying raw configuration lines into the report, reducing the risk of leaking credentials or customer network details. It does not connect to devices, execute commands, certify compliance, or make configuration changes. Vendor syntax varies by model and software version; review the checks before relying on them.
