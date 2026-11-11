from datetime import datetime, timezone
from pathlib import Path
import json
import re
import uuid

ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = ROOT / "data" / "tasks"

def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:36] or "task"

def create_task(description: str) -> dict:
    description = description.strip()
    if not description:
        raise ValueError("Task description cannot be empty")
    task_id = f"{_slug(description)}-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "task_id": task_id, "description": description, "status": "planned",
        "owner": "ceo-orchestrator", "created_at": now, "execution_mode": "dry_run",
        "approval_required": True,
        "approval_reason": "Initial scaffold does not execute agent actions.",
        "acceptance_criteria": [
            "Scope and expected outcome are documented",
            "Risks and required permissions are identified",
            "QA evidence is attached before completion"
        ],
        "events": [{"type": "task_created", "at": now}]
    }
    TASK_DIR.mkdir(parents=True, exist_ok=True)
    (TASK_DIR / f"{task_id}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return record

def doctor() -> list[str]:
    return [
        "Python runtime: OK", f"Project root: {ROOT}",
        "Task mode: dry-run only", "Shell execution: disabled",
        "External integrations: not configured",
        "Human approval gates: documented"
    ]
