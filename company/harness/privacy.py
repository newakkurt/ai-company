"""Sensitive-data detection and redaction (KVKK/GDPR, secrets, internal data).

Findings never contain the matched value, only its kind and count, so a finding
list is always safe to log.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    kind: str
    count: int


def _luhn_ok(digits: str) -> bool:
    total, parity = 0, len(digits) % 2
    for index, char in enumerate(digits):
        number = int(char)
        if index % 2 == parity:
            number *= 2
            if number > 9:
                number -= 9
        total += number
    return total % 10 == 0


def _tc_kimlik_ok(digits: str) -> bool:
    """Official TC Kimlik No checksum; filters random 11-digit numbers."""
    if len(digits) != 11 or digits[0] == "0":
        return False
    d = [int(c) for c in digits]
    if ((sum(d[0:9:2]) * 7) - sum(d[1:8:2])) % 10 != d[9]:
        return False
    return sum(d[:10]) % 10 == d[10]


_PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
_API_KEY = re.compile(
    r"\b(?:sk-[A-Za-z0-9_-]{16,}|gsk_[A-Za-z0-9]{16,}|AIza[0-9A-Za-z_-]{30,}|"
    r"gh[pousr]_[A-Za-z0-9]{30,}|xox[baprs]-[A-Za-z0-9-]{10,}|"
    r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})\b"
)
_SECRET_ASSIGN = re.compile(
    r"(?i)\b(?:password|passwd|parola|şifre|sifre|secret|token|api[_-]?key|"
    r"community|snmp-agent community(?: read| write)?|enable secret|"
    r"pre-shared-key|cipher)\b\s*[:=]?\s*(?:\d\s+)?[^\s,;'\"]{4,}"
)
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}(?:\s?[A-Z0-9]{1,4})?\b")
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_TR = re.compile(r"(?<!\d)(?:\+?90[\s-]?|0)?5\d{2}[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}(?!\d)")
_INTERNAL_IP = re.compile(
    r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|"
    r"172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"
)
_DIGIT_RUN = re.compile(r"(?<![\d.])\d(?:[ -]?\d){10,18}(?![\d.])")
_CONFIDENTIAL = re.compile(
    r"(?i)\b(?:gizli|çok gizli|confidential|internal only|kurum içi|kvkk|"
    r"kişisel veri|maaş bordrosu|müşteri listesi|finansal kayıt)\b"
)


def _digit_matches(text: str):
    for match in _DIGIT_RUN.finditer(text):
        yield match, re.sub(r"\D", "", match.group())


def scan(text: str) -> list[Finding]:
    """Return the kinds of sensitive data found in *text* (never the values)."""
    text = text or ""
    counts: dict[str, int] = {}

    def add(kind: str, amount: int = 1):
        if amount:
            counts[kind] = counts.get(kind, 0) + amount

    add("private_key", len(_PRIVATE_KEY.findall(text)))
    add("api_key", len(_API_KEY.findall(text)))
    add("secret_assignment", len(_SECRET_ASSIGN.findall(text)))
    add("iban", len(_IBAN.findall(text)))
    add("email", len(_EMAIL.findall(text)))
    add("phone_tr", len(_PHONE_TR.findall(text)))
    add("internal_ip", len(_INTERNAL_IP.findall(text)))
    add("confidential_marker", len(_CONFIDENTIAL.findall(text)))
    for _match, digits in _digit_matches(text):
        if _tc_kimlik_ok(digits):
            add("tc_kimlik")
        elif 13 <= len(digits) <= 19 and _luhn_ok(digits):
            add("payment_card")
    return [Finding(kind, count) for kind, count in sorted(counts.items())]


def is_sensitive(text: str) -> bool:
    return bool(scan(text))


def redact(text: str) -> tuple[str, list[Finding]]:
    """Mask sensitive values; returns (safe_text, findings)."""
    text = text or ""
    findings = scan(text)
    if not findings:
        return text, findings
    text = _PRIVATE_KEY.sub("[REDACTED:private_key]", text)
    text = _API_KEY.sub("[REDACTED:api_key]", text)
    text = _SECRET_ASSIGN.sub(lambda m: m.group().split()[0] + " [REDACTED:secret]", text)
    text = _IBAN.sub("[REDACTED:iban]", text)
    text = _EMAIL.sub("[REDACTED:email]", text)
    text = _PHONE_TR.sub("[REDACTED:phone]", text)
    text = _INTERNAL_IP.sub("[REDACTED:internal_ip]", text)

    def mask_digits(match):
        digits = re.sub(r"\D", "", match.group())
        if _tc_kimlik_ok(digits):
            return "[REDACTED:tc_kimlik]"
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            return "[REDACTED:payment_card]"
        return match.group()

    return _DIGIT_RUN.sub(mask_digits, text), findings


def summarize(findings: list[Finding]) -> dict[str, int]:
    return {finding.kind: finding.count for finding in findings}
