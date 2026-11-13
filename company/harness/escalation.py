"""Checkpoints, 3-attempt limit and SQLite human review queue (principle 3)."""
from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .privacy import redact, scan

ROOT = Path(__file__).resolve().parents[2]
MAX_ATTEMPTS = 3

HIGH_RISK = {
    "financial": re.compile(r"(?i)\b(?:iade|refund|chargeback|geri ödeme|ödeme iadesi|fatura iptali|"
                            r"payout|transfer|havale|eft)\b"),
    "legal": re.compile(r"(?i)\b(?:hukuk|dava|sözleşme feshi|ihtar|legal advice|lawsuit|"
                        r"kvkk ihlali|data breach|veri ihlali|savcılık|mahkeme)\b"),
    "destructive": re.compile(r"(?i)\b(?:delete (?:all|production)|toplu sil|drop database|wipe|"
                              r"format disk|factory reset)\b"),
    "network_change": re.compile(r"(?i)\b(?:production switch|canlı switch|core switch|"
                                 r"push config|write erase|reload device)\b"),
}


def classify_risk(text: str) -> list[str]:
    """Return categories that must go to a human (empty list = automatable)."""
    return [name for name, pattern in HIGH_RISK.items() if pattern.search(text or "")]


def db_path() -> Path:
    return Path(os.getenv("AI_COMPANY_REVIEW_DB") or (ROOT / "data" / "human_review.db"))


class HumanReviewQueue:
    """Durable Supabase approval_requests queue in hosted mode; SQLite locally."""

    def __init__(self, path: Path | str | None = None, store=None):
        self._store = store
        if self._store is None and path is None and all(os.getenv(key) for key in (
            "SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_DB_GATE_KEY"
        )):
            from ..store import SupabaseTaskStore
            self._store = SupabaseTaskStore()
        self.path = Path(path) if path else db_path()
        if self._store is not None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS human_review_queue (
                review_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, reason TEXT NOT NULL,
                categories TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','approved','rejected')),
                created_at TEXT NOT NULL, decided_at TEXT, decided_by TEXT, note TEXT)""")
            db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS ux_review_pending
                ON human_review_queue(task_id, reason) WHERE status='pending'""")

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    @staticmethod
    def _from_cloud(row: dict) -> dict:
        scope = row.get("scope_json") or {}
        return {
            "review_id": row["approval_id"],
            "task_id": scope.get("task_id", ""),
            "reason": scope.get("reason", ""),
            "categories": json.dumps(scope.get("categories") or [], ensure_ascii=False),
            "attempts": int(scope.get("attempts") or 0),
            "payload": json.dumps(scope.get("payload") or {}, ensure_ascii=False),
            "status": row.get("status", "pending"),
            "created_at": row.get("requested_at"),
            "decided_at": row.get("decided_at"),
            "decided_by": row.get("decided_by"),
            "note": row.get("decision_note"),
        }

    def enqueue(self, task_id: str, reason: str, payload: dict | None = None,
                categories: list[str] | None = None, attempts: int = 0) -> str:
        """Idempotent per (task_id, reason); payload is redacted before persistence."""
        safe = redact(json.dumps(payload or {}, ensure_ascii=False, default=str))[0]
        if self._store is not None:
            safe_payload = json.loads(safe)
            rows = self._store._request("approval_requests", params={
                "select": "approval_id,scope_json,status", "action": "eq.human_review",
                "status": "eq.pending", "order": "requested_at.desc", "limit": "500",
            })
            for row in rows:
                scope = row.get("scope_json") or {}
                if scope.get("task_id") == task_id and scope.get("reason") == reason:
                    return row["approval_id"]
            review_id = "review-" + uuid.uuid4().hex
            now = datetime.now(timezone.utc)
            self._store._request("approval_requests", "POST", body={
                "approval_id": review_id, "action": "human_review",
                "scope_json": {
                    "task_id": task_id, "reason": reason,
                    "categories": categories or [], "attempts": attempts,
                    "payload": safe_payload,
                },
                "requested_by": "agent_harness", "status": "pending",
                "requested_at": now.isoformat(),
                "expires_at": (now + timedelta(days=365)).isoformat(),
            }, prefer="return=minimal")
            return review_id

        review_id = "rev-" + uuid.uuid4().hex[:12]
        with closing(self._connect()) as db, db:
            existing = db.execute("SELECT review_id FROM human_review_queue WHERE task_id=? AND reason=? "
                                  "AND status='pending'", (task_id, reason)).fetchone()
            if existing:
                return existing["review_id"]
            db.execute("INSERT INTO human_review_queue (review_id,task_id,reason,categories,attempts,"
                       "payload,created_at) VALUES (?,?,?,?,?,?,?)",
                       (review_id, task_id, reason, json.dumps(categories or []), attempts, safe,
                        datetime.now(timezone.utc).isoformat()))
        return review_id

    def list(self, status: str | None = "pending", limit: int = 100) -> list[dict]:
        if self._store is not None:
            params = {
                "select": "approval_id,scope_json,status,requested_at,decided_at,decided_by,decision_note",
                "action": "eq.human_review", "order": "requested_at.asc",
                "limit": str(max(1, min(int(limit), 500))),
            }
            if status:
                params["status"] = f"eq.{status}"
            return [self._from_cloud(row) for row in self._store._request("approval_requests", params=params)]
        sql, args = "SELECT * FROM human_review_queue", []
        if status:
            sql += " WHERE status=?"
            args.append(status)
        sql += " ORDER BY created_at ASC LIMIT ?"
        args.append(limit)
        with closing(self._connect()) as db:
            return [dict(row) for row in db.execute(sql, args)]

    def get(self, review_id: str) -> dict | None:
        if self._store is not None:
            rows = self._store._request("approval_requests", params={
                "select": "approval_id,scope_json,status,requested_at,decided_at,decided_by,decision_note",
                "approval_id": f"eq.{review_id}", "action": "eq.human_review", "limit": "1",
            })
            return self._from_cloud(rows[0]) if rows else None
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM human_review_queue WHERE review_id=?", (review_id,)).fetchone()
        return dict(row) if row else None

    def decide(self, review_id: str, decision: str, actor: str, note: str = "") -> dict:
        if decision not in {"approved", "rejected"}:
            raise ValueError("decision must be 'approved' or 'rejected'")
        if self._store is not None:
            now = datetime.now(timezone.utc).isoformat()
            rows = self._store._request("approval_requests", "PATCH", {
                "approval_id": f"eq.{review_id}", "action": "eq.human_review",
                "status": "eq.pending", "expires_at": f"gt.{now}",
            }, {"status": decision, "decided_at": now, "decided_by": actor,
                "decision_note": note[:1000]}, "return=representation")
            if not rows:
                raise KeyError(f"No pending review: {review_id}")
            return self._from_cloud(rows[0])
        with closing(self._connect()) as db, db:
            changed = db.execute(
                "UPDATE human_review_queue SET status=?, decided_at=?, decided_by=?, note=? "
                "WHERE review_id=? AND status='pending'",
                (decision, datetime.now(timezone.utc).isoformat(), actor, note[:500], review_id)).rowcount
        if not changed:
            raise KeyError(f"No pending review: {review_id}")
        return self.get(review_id)


# ---- verification checkpoints -------------------------------------------------

@dataclass
class CheckResult:
    ok: bool
    reasons: list = field(default_factory=list)


def verify_output(text: str, *, min_chars: int = 1, required_markers: tuple = (),
                  forbid_secrets: bool = True) -> CheckResult:
    """Checkpoint between steps: a tool/agent output must pass before the next step runs."""
    reasons = []
    text = text or ""
    if len(text.strip()) < min_chars:
        reasons.append("output_too_short")
    for marker in required_markers:
        if marker.casefold() not in text.casefold():
            reasons.append(f"missing_marker:{marker}")
    if forbid_secrets:
        leaked = [f.kind for f in scan(text) if f.kind in {"private_key", "api_key", "secret_assignment"}]
        reasons.extend(f"secret_leak:{kind}" for kind in leaked)
    return CheckResult(not reasons, reasons)


# ---- bounded retry loop ---------------------------------------------------------

@dataclass
class Outcome:
    status: str                      # "ok" | "escalated"
    result: object = None
    attempts: int = 0
    errors: list = field(default_factory=list)
    review_id: str | None = None


def run_with_retries(func, *, task_id: str, description: str = "", queue: HumanReviewQueue | None = None,
                     max_attempts: int = MAX_ATTEMPTS, verify=None, sleeper=None) -> Outcome:
    """Run *func* at most *max_attempts* (hard cap 3) times, verifying each result.

    High-risk/subjective work is escalated before the first attempt; exhausted work
    is escalated after the last. Nothing loops beyond the cap.
    """
    queue = queue or HumanReviewQueue()
    max_attempts = max(1, min(int(max_attempts), MAX_ATTEMPTS))
    categories = classify_risk(description)
    if categories:
        review_id = queue.enqueue(task_id, "high_risk_requires_human", {"description": description[:500]},
                                  categories, 0)
        return Outcome("escalated", None, 0, [], review_id)
    errors: list[str] = []
    for attempt in range(1, max_attempts + 1):
        try:
            result = func()
            check = verify(result) if verify else CheckResult(True)
            if check.ok:
                return Outcome("ok", result, attempt, errors)
            errors.append("verification_failed:" + ",".join(check.reasons))
        except Exception as exc:  # noqa: BLE001 - recorded by class only
            errors.append(type(exc).__name__)
        if sleeper and attempt < max_attempts:
            sleeper(min(2 ** attempt, 30))
    review_id = queue.enqueue(task_id, "retry_budget_exhausted",
                              {"description": description[:500], "errors": errors}, [], max_attempts)
    return Outcome("escalated", None, max_attempts, errors, review_id)
