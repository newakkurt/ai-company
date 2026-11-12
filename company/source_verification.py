"""Safe public HTTPS source verification for AI-discovered company leads.

The verifier pins each outbound connection to a resolved public IP, validates
redirect targets independently, caps response size and never follows private
or local addresses. A reachable page is evidence for review, not proof of identity.
"""
from __future__ import annotations

import http.client
import ipaddress
import re
import socket
import ssl
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit


MAX_BODY_BYTES = 250_000
MAX_REDIRECTS = 3
TIMEOUT_SECONDS = 8
BLOCKED_SUFFIXES = (
    ".localhost", ".local", ".internal", ".test", ".invalid",
    ".example", ".example.com", ".example.org", ".example.net",
)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, pinned_ip: str, timeout: int = TIMEOUT_SECONDS):
        super().__init__(host, port=443, timeout=timeout, context=ssl.create_default_context())
        self._pinned_ip = pinned_ip

    def connect(self):
        raw = socket.create_connection((self._pinned_ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(raw, server_hostname=self.host)


class _PageText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_title = False
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data):
        value = data.strip()
        if not value:
            return
        self.text_parts.append(value)
        if self.in_title:
            self.title_parts.append(value)


def _normalise(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _public_addresses(host: str, resolver=None) -> list[str]:
    resolver = resolver or socket.getaddrinfo
    answers = resolver(host, 443, type=socket.SOCK_STREAM)
    addresses = sorted({str(item[4][0]).split("%", 1)[0] for item in answers})
    if not addresses:
        raise ValueError("DNS returned no addresses")
    for address in addresses:
        parsed = ipaddress.ip_address(address)
        if not parsed.is_global:
            raise PermissionError("DNS resolved to a non-public IP address")
    return addresses


def _validate_url(url: str):
    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise PermissionError("Only public HTTPS source URLs are allowed")
    if parsed.username or parsed.password or parsed.port not in (None, 443):
        raise PermissionError("URL credentials and non-standard ports are not allowed")
    host = parsed.hostname.rstrip(".").lower()
    if any(host == suffix.lstrip(".") or host.endswith(suffix) for suffix in BLOCKED_SUFFIXES):
        raise PermissionError("Local, test and placeholder domains are not allowed")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise PermissionError("IP-literal source URLs are not allowed")
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    return host, path


def verify_public_source(
    url: str,
    company_name: str,
    resolver=None,
    connection_factory=None,
) -> dict:
    """Return a bounded verification record; never treat reachability as human approval."""
    checked_at = datetime.now(timezone.utc).isoformat()
    current = str(url or "").strip()
    connection_factory = connection_factory or _PinnedHTTPSConnection
    last_status = None
    try:
        for redirect_count in range(MAX_REDIRECTS + 1):
            host, path = _validate_url(current)
            addresses = _public_addresses(host, resolver)
            connection = connection_factory(host, addresses[0], timeout=TIMEOUT_SECONDS)
            try:
                connection.request("GET", path, headers={
                    "Host": host,
                    "User-Agent": "NewAkkurtCompanySourceVerifier/1.0",
                    "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.7",
                    "Connection": "close",
                })
                response = connection.getresponse()
                last_status = int(response.status)
                if last_status in (301, 302, 303, 307, 308):
                    location = response.getheader("Location")
                    if not location:
                        return {
                            "source_validation_status": "unreachable",
                            "source_http_status": last_status,
                            "source_page_title": None,
                            "source_checked_at": checked_at,
                            "source_validation_note": "Redirect response did not include a Location header.",
                        }
                    if redirect_count >= MAX_REDIRECTS:
                        return {
                            "source_validation_status": "redirect_limit",
                            "source_http_status": last_status,
                            "source_page_title": None,
                            "source_checked_at": checked_at,
                            "source_validation_note": "Source exceeded the redirect limit.",
                        }
                    current = urljoin(current, location)
                    continue
                if last_status != 200:
                    return {
                        "source_validation_status": "unreachable",
                        "source_http_status": last_status,
                        "source_page_title": None,
                        "source_checked_at": checked_at,
                        "source_validation_note": f"Source returned HTTP {last_status}.",
                    }
                content_type = response.getheader("Content-Type", "").lower()
                if not any(kind in content_type for kind in ("text/html", "application/xhtml+xml")):
                    return {
                        "source_validation_status": "reachable_unparsed",
                        "source_http_status": last_status,
                        "source_page_title": None,
                        "source_checked_at": checked_at,
                        "source_validation_note": f"Source is reachable but has unsupported content type: {content_type[:100]}.",
                    }
                length = response.getheader("Content-Length")
                if length and int(length) > MAX_BODY_BYTES:
                    return {
                        "source_validation_status": "too_large",
                        "source_http_status": last_status,
                        "source_page_title": None,
                        "source_checked_at": checked_at,
                        "source_validation_note": "Source page exceeds the 250 KB verification limit.",
                    }
                body = response.read(MAX_BODY_BYTES + 1)
                if len(body) > MAX_BODY_BYTES:
                    return {
                        "source_validation_status": "too_large",
                        "source_http_status": last_status,
                        "source_page_title": None,
                        "source_checked_at": checked_at,
                        "source_validation_note": "Source page exceeds the 250 KB verification limit.",
                    }
                parser = _PageText()
                parser.feed(body.decode("utf-8", errors="replace"))
                title = " ".join(parser.title_parts)[:250] or None
                text = _normalise(" ".join(parser.text_parts))
                tokens = [token for token in _normalise(company_name).split() if len(token) >= 4]
                matched = any(token in text for token in tokens) if tokens else False
                status = "reachable_match" if matched else "reachable_no_match"
                return {
                    "source_validation_status": status,
                    "source_http_status": last_status,
                    "source_page_title": title,
                    "source_checked_at": checked_at,
                    "source_validation_note": (
                        "HTTP 200; company-name token found in page text."
                        if matched else "HTTP 200; company name was not found in the page text."
                    ),
                }
            finally:
                connection.close()
        return {
            "source_validation_status": "redirect_limit",
            "source_http_status": last_status,
            "source_page_title": None,
            "source_checked_at": checked_at,
            "source_validation_note": "Source exceeded the redirect limit.",
        }
    except PermissionError as exc:
        status = "unsafe_url"
        note = str(exc)
    except (OSError, ValueError, ssl.SSLError, http.client.HTTPException) as exc:
        status = "unreachable"
        note = f"Source check failed: {type(exc).__name__}."
    except Exception as exc:  # noqa: BLE001 - external source data must not crash the worker
        status = "unreachable"
        note = f"Source check failed: {type(exc).__name__}."
    return {
        "source_validation_status": status,
        "source_http_status": last_status,
        "source_page_title": None,
        "source_checked_at": checked_at,
        "source_validation_note": note[:500],
    }
