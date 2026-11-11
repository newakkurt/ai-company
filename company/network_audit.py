"""Read-only, evidence-backed first-pass switch configuration audit.

This module never connects to devices and never applies configuration changes.
Findings describe text evidence only; absence from a partial config is not proof
that a control is absent on the live device.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Iterable


@dataclass(frozen=True)
class Finding:
    check_id: str
    severity: str
    title: str
    detail: str
    evidence: tuple[str, ...]
    recommendation: str


@dataclass(frozen=True)
class AuditResult:
    vendor: str
    findings: tuple[Finding, ...]
    notes: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "vendor": self.vendor,
            "finding_count": len(self.findings),
            "findings": [asdict(item) for item in self.findings],
            "notes": list(self.notes),
            "mode": "read_only_text_analysis",
        }


def detect_vendor(config: str) -> str:
    text = config.casefold()
    if any(token in text for token in ("sysname ", "undo ", "stelnet", "interface vlanif")):
        return "huawei"
    if any(token in text for token in ("version ", "switchport ", "hostname ", "line vty")):
        return "cisco"
    if any(token in text for token in ("aruba", "procurve", "trunk ", "vlan ")) and "interface " in text:
        return "aruba_or_legacy_procurve"
    return "unknown"


def _matching_lines(lines: Iterable[str], patterns: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(line.strip() for line in lines if any(re.search(p, line, re.I) for p in patterns))


def _interface_blocks(lines: list[str], vendor: str) -> list[tuple[str, list[str]]]:
    blocks: list[tuple[str, list[str]]] = []
    current_name: str | None = None
    current: list[str] = []
    for raw in lines:
        stripped = raw.strip()
        if vendor == "huawei":
            starts = bool(re.match(r"^interface\s+\S+", stripped, re.I))
            ends = stripped.casefold() == "quit"
        else:
            starts = bool(re.match(r"^interface\s+\S+", stripped, re.I))
            ends = stripped.casefold() == "!"
        if starts:
            if current_name is not None:
                blocks.append((current_name, current))
            current_name, current = stripped.split(None, 1)[1], []
        elif ends and current_name is not None:
            blocks.append((current_name, current))
            current_name, current = None, []
        elif current_name is not None:
            current.append(stripped)
    if current_name is not None:
        blocks.append((current_name, current))
    return blocks


def audit_config(config: str, vendor: str | None = None) -> AuditResult:
    if not isinstance(config, str) or not config.strip():
        raise ValueError("Configuration text is required")
    lines = [line.rstrip() for line in config.splitlines() if line.strip()]
    detected = vendor or detect_vendor(config)
    normalized = detected.casefold()
    findings: list[Finding] = []
    notes = [
        "Analysis is limited to the supplied text; partial or sanitized configs can create false positives.",
        "No device connection, command execution, configuration change, or shutdown action is performed.",
    ]

    checks = [
        ("management.ntp", "NTP configuration not found", "medium",
         (r"\bntp\b", r"clock protocol ntp", r"ntp-service"),
         "Confirm the device uses approved, reachable time sources."),
        ("management.logging", "Remote logging configuration not found", "medium",
         (r"\blogging\s+(host|\d)", r"info-center loghost", r"logging\s+\S+"),
         "Configure the approved central syslog destination and validate delivery."),
        ("management.aaa", "AAA configuration not found", "medium",
         (r"\baaa\b", r"authentication-scheme", r"radius-server", r"tacacs"),
         "Review centralized authentication and local break-glass access."),
    ]
    for check_id, title, severity, patterns, recommendation in checks:
        evidence = _matching_lines(lines, patterns)
        if not evidence:
            findings.append(Finding(
                check_id, severity, title,
                "No matching directive was found in the supplied configuration.",
                (), recommendation,
            ))

    insecure = _matching_lines(lines, (
        r"transport input .*\btelnet\b",
        r"telnet server enable",
        r"undo ssh server-source",
    ))
    if insecure:
        findings.append(Finding(
            "management.telnet", "high", "Telnet-related directive found",
            "The supplied text contains a directive that may enable or permit Telnet.",
            insecure, "Verify management-plane exposure and prefer SSH; remove Telnet only through an approved change.",
        ))

    blocks = _interface_blocks(lines, normalized)
    undocumented = []
    for name, body in blocks:
        if not any(re.match(r"^description\s+\S+", item, re.I) for item in body):
            if not any(re.match(r"^shutdown$", item, re.I) for item in body):
                undocumented.append(f"interface {name}")
    if undocumented:
        findings.append(Finding(
            "interfaces.missing_description", "low",
            "Interfaces without descriptions found",
            f"{len(undocumented)} interface block(s) have no description directive in the supplied text.",
            tuple(undocumented[:50]),
            "Confirm port purpose with the owner and document it; do not infer that an undocumented port is unused.",
        ))

    if not blocks:
        notes.append("No interface blocks were parsed; interface-level checks were skipped.")
    if normalized == "unknown":
        notes.append("Vendor could not be identified confidently; generic text checks only were applied.")

    return AuditResult(normalized, tuple(findings), tuple(notes))
