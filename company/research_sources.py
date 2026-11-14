"""Keyless, free, public demand evidence for the research roles.

The Groq models used by the worker cannot browse. Instead of letting them write
market claims from memory, fetch real public signals (most-voted recent questions
from Stack Exchange network/server sites and recent Hacker News stories) and hand
them to the model as quoted evidence with URLs. Read-only HTTPS GETs of public APIs;
no credentials, no personal data, nothing is posted anywhere.

Everything fails soft: any network or parsing error yields an empty string and the
analysis simply states that no live evidence was available.
"""
from __future__ import annotations

import gzip
import html
import json
import os
import threading
import time
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

USER_AGENT = "ai-company-research/1.0 (public read-only demand research)"
CACHE_TTL_SECONDS = 6 * 3600
EVIDENCE_CHAR_BUDGET = 2600
REQUEST_TIMEOUT = 12

# (site, query) pairs rotated by day so repeated runs cover different ground.
STACK_TOPICS = [
    ("networkengineering", "network configuration backup"),
    ("networkengineering", "switch configuration audit"),
    ("networkengineering", "network automation"),
    ("networkengineering", "vlan troubleshooting"),
    ("networkengineering", "snmp monitoring"),
    ("serverfault", "network monitoring alerts"),
]
HN_QUERIES = ["network automation", "network monitoring", "configuration management", "network security tool"]

_cache: dict[str, tuple[float, list[dict]]] = {}
_lock = threading.Lock()


def evidence_enabled() -> bool:
    return os.getenv("AI_COMPANY_WEB_EVIDENCE", "true").strip().lower() not in {"0", "false", "no", "off"}


def _get_json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json",
                                    "Accept-Encoding": "gzip"})
    with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        raw = response.read()
        if response.headers.get("Content-Encoding", "").lower() == "gzip" or raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))


def _cached(key: str, loader, now: float) -> list[dict]:
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < CACHE_TTL_SECONDS:
            return hit[1]
    items = loader()
    with _lock:
        _cache[key] = (now, items)
    return items


def _stack_items(site: str, query: str, since_ts: int, fetch) -> list[dict]:
    url = "https://api.stackexchange.com/2.3/search/advanced?" + urlencode({
        "order": "desc", "sort": "votes", "q": query, "site": site,
        "pagesize": 5, "fromdate": since_ts,
    })
    data = fetch(url)
    items = []
    for row in data.get("items", [])[:5]:
        items.append({
            "source": f"stackexchange:{site}", "title": html.unescape(str(row.get("title", ""))).strip(),
            "score": int(row.get("score", 0)), "replies": int(row.get("answer_count", 0)),
            "views": int(row.get("view_count", 0)), "url": str(row.get("link", "")),
            "date": int(row.get("creation_date", 0)),
        })
    return items


def _hn_items(query: str, since_ts: int, fetch) -> list[dict]:
    url = "https://hn.algolia.com/api/v1/search?" + urlencode({
        "query": query, "tags": "story", "hitsPerPage": 5,
        "numericFilters": f"created_at_i>{since_ts},points>5",
    })
    data = fetch(url)
    items = []
    for row in data.get("hits", [])[:5]:
        object_id = row.get("objectID")
        if not object_id or not row.get("title"):
            continue
        items.append({
            "source": "hackernews", "title": html.unescape(str(row["title"])).strip(),
            "score": int(row.get("points") or 0), "replies": int(row.get("num_comments") or 0),
            "views": 0, "url": f"https://news.ycombinator.com/item?id={object_id}",
            "date": int(row.get("created_at_i") or 0),
        })
    return items


def collect(now: datetime | None = None, fetch=None) -> list[dict]:
    """Return de-duplicated evidence items, best first. Never raises."""
    now = now or datetime.now(timezone.utc)
    fetch = fetch or _get_json
    ts = time.time()
    since = int(now.timestamp()) - 365 * 86400
    day = now.toordinal()
    picks = [STACK_TOPICS[day % len(STACK_TOPICS)], STACK_TOPICS[(day + 1) % len(STACK_TOPICS)]]
    hn_query = HN_QUERIES[day % len(HN_QUERIES)]
    jobs = [(f"se|{s}|{q}", lambda s=s, q=q: _stack_items(s, q, since, fetch)) for s, q in picks]
    jobs.append((f"hn|{hn_query}", lambda: _hn_items(hn_query, since, fetch)))
    items: list[dict] = []
    for key, loader in jobs:
        try:
            items.extend(_cached(key, loader, ts))
        except Exception as exc:  # network, quota, malformed JSON: degrade silently
            print(f"agent_worker: web evidence source failed key={key} error={type(exc).__name__}", flush=True)
    seen, unique = set(), []
    for item in sorted(items, key=lambda i: (i["score"], i["replies"]), reverse=True):
        if item["url"] and item["url"] not in seen:
            seen.add(item["url"])
            unique.append(item)
    return unique


def format_evidence(items: list[dict], budget: int = EVIDENCE_CHAR_BUDGET, retrieved: str | None = None) -> str:
    """Compact, citation-ready block. Empty string when there is nothing to show."""
    if not items:
        return ""
    retrieved = retrieved or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [
        f"Live public evidence (retrieved {retrieved}; real questions/stories, not opinions). "
        "Cite only these URLs; do not invent others. Scores are community upvotes, not market size."
    ]
    used = len(lines[0])
    for item in items:
        day = datetime.fromtimestamp(item["date"], timezone.utc).strftime("%Y-%m") if item["date"] else "?"
        line = (f"- [{item['source']}] {item['title'][:140]} | score={item['score']} "
                f"replies={item['replies']} {day} | {item['url']}")
        if used + len(line) + 1 > budget:
            break
        lines.append(line)
        used += len(line) + 1
    return "\n".join(lines) if len(lines) > 1 else ""


def demand_evidence_block(now: datetime | None = None, fetch=None) -> tuple[str, int]:
    """(prompt block, item count). ('', 0) when disabled or unavailable."""
    if not evidence_enabled():
        return "", 0
    items = collect(now=now, fetch=fetch)
    block = format_evidence(items)
    return block, (block.count("\n") if block else 0)
