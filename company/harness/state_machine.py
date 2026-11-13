"""Explicit task state machine with a tamper-evident decision trace (principle 2).

Every transition is validated against TRANSITIONS and appended to a JSONL trace
(`data/traces/<task_id>.jsonl`). Records are hash-chained so a later edit or
deletion is detectable with verify_trace(). Parameters are redacted before
being written.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from .privacy import redact

ROOT = Path(__file__).resolve().parents[2]


class State(str, Enum):
    RECEIVED = "received"
    PLANNED = "planned"
    SUGGESTED_ASSIGNMENTS = "suggested_assignments"
    RUNNING = "running"
    ANALYSIS_ONLY = "analysis_only"
    QA_REVIEW = "qa_review"
    APPROVAL_REQUIRED = "approval_required"
    APPROVED_FOR_NEXT_STEP = "approved_for_next_step"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    ESCALATED = "escalated"   # waiting in the human review queue
    REJECTED = "rejected"
    FAILED = "failed"


S = State
TRANSITIONS: dict[State, frozenset] = {
    S.RECEIVED: frozenset({S.PLANNED, S.BLOCKED, S.ESCALATED, S.REJECTED}),
    S.PLANNED: frozenset({S.SUGGESTED_ASSIGNMENTS, S.RUNNING, S.BLOCKED, S.ESCALATED}),
    S.SUGGESTED_ASSIGNMENTS: frozenset({S.RUNNING, S.ANALYSIS_ONLY, S.BLOCKED, S.ESCALATED}),
    S.RUNNING: frozenset({S.ANALYSIS_ONLY, S.QA_REVIEW, S.COMPLETED, S.FAILED, S.BLOCKED, S.ESCALATED}),
    S.ANALYSIS_ONLY: frozenset({S.QA_REVIEW, S.COMPLETED, S.FAILED, S.ESCALATED}),
    S.QA_REVIEW: frozenset({S.APPROVAL_REQUIRED, S.COMPLETED, S.FAILED, S.ESCALATED}),
    S.APPROVAL_REQUIRED: frozenset({S.APPROVED_FOR_NEXT_STEP, S.REJECTED, S.ESCALATED}),
    S.APPROVED_FOR_NEXT_STEP: frozenset({S.COMPLETED}),
    S.BLOCKED: frozenset({S.PLANNED, S.ESCALATED, S.REJECTED}),
    S.ESCALATED: frozenset({S.PLANNED, S.REJECTED, S.APPROVED_FOR_NEXT_STEP}),
    S.FAILED: frozenset({S.PLANNED, S.ESCALATED}),        # bounded retry or human queue
    S.COMPLETED: frozenset(),
    S.REJECTED: frozenset(),
}
TERMINAL = frozenset(state for state, nxt in TRANSITIONS.items() if not nxt)


class InvalidTransition(ValueError):
    pass


def _state(value) -> State:
    return value if isinstance(value, State) else State(str(value))


def can_transition(src, dst) -> bool:
    return _state(dst) in TRANSITIONS[_state(src)]


def trace_dir() -> Path:
    return Path(os.getenv("AI_COMPANY_TRACE_DIR") or (ROOT / "data" / "traces"))


_SAFE_ID = re.compile(r"[^A-Za-z0-9._-]+")
_lock = threading.Lock()
GENESIS = "0" * 64


def _trace_path(task_id: str, directory: Path | None = None) -> Path:
    return (directory or trace_dir()) / (_SAFE_ID.sub("_", task_id)[:120] + ".jsonl")


def _hash(record: dict) -> str:
    body = {k: v for k, v in record.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def read_trace(task_id: str, directory: Path | None = None) -> list[dict]:
    path = _trace_path(task_id, directory)
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def record_transition(task_id: str, src, dst, trigger: str, params: dict | None = None,
                      directory: Path | None = None, enforce: bool = True) -> dict:
    """Validate and persist one transition. Raises InvalidTransition when illegal."""
    src, dst = _state(src), _state(dst)
    if enforce and dst not in TRANSITIONS[src]:
        raise InvalidTransition(f"{src.value} -> {dst.value} is not allowed")
    safe_params = json.loads(redact(json.dumps(params or {}, ensure_ascii=False, default=str))[0])
    with _lock:
        existing = read_trace(task_id, directory)
        record = {
            "seq": len(existing) + 1,
            "ts": datetime.now(timezone.utc).isoformat(),
            "task_id": task_id,
            "from": src.value, "to": dst.value,
            "trigger": trigger,
            "params": safe_params,
            "prev_hash": existing[-1]["hash"] if existing else GENESIS,
        }
        record["hash"] = _hash(record)
        path = _trace_path(task_id, directory)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return record


def verify_trace(task_id: str, directory: Path | None = None) -> tuple[bool, str]:
    """Check hash chain, sequence numbers and transition legality."""
    previous, expected_state = GENESIS, None
    for index, record in enumerate(read_trace(task_id, directory), 1):
        if record.get("seq") != index:
            return False, f"sequence gap at {index}"
        if record.get("prev_hash") != previous or record.get("hash") != _hash(record):
            return False, f"hash mismatch at {index}"
        if expected_state is not None and record["from"] != expected_state:
            return False, f"state discontinuity at {index}"
        try:
            if not can_transition(record["from"], record["to"]):
                return False, f"illegal transition at {index}"
        except ValueError:
            return False, f"unknown state at {index}"
        previous, expected_state = record["hash"], record["to"]
    return True, "ok"


class TaskMachine:
    """Convenience wrapper that tracks the current state of one task."""

    def __init__(self, task_id: str, state=State.RECEIVED, directory: Path | None = None):
        self.task_id, self.state, self.directory = task_id, _state(state), directory

    def to(self, dst, trigger: str, **params) -> dict:
        record = record_transition(self.task_id, self.state, dst, trigger, params, self.directory)
        self.state = _state(dst)
        return record

    @property
    def terminal(self) -> bool:
        return self.state in TERMINAL


def safe_record(task_id: str, src, dst, trigger: str, **params):
    """Best-effort tracing for production paths: never raises, never alters task outcome."""
    try:
        return record_transition(task_id, src, dst, trigger, params, enforce=False)
    except Exception as exc:  # noqa: BLE001
        print(f"trace: write failed; error_type={type(exc).__name__}", flush=True)
        return None
