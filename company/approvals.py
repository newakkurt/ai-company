"""Policy-backed, one-time human approval checks for side-effecting actions."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any


POLICY_PATH = Path(__file__).resolve().parent / "policies" / "approval_matrix.yml"


class ApprovalError(ValueError):
    """Base class for denied or missing action approvals."""


class ApprovalRequiredError(ApprovalError):
    """Raised when a protected action has no matching approved request."""


class ApprovalDeniedError(ApprovalError):
    """Raised when an approval is rejected, expired, mismatched, or already used."""


def load_approval_matrix(path: Path | str = POLICY_PATH) -> dict[str, bool]:
    """Read the deliberately small YAML subset used by approval_matrix.yml."""
    matrix: dict[str, bool] = {}
    text = Path(path).read_text(encoding="utf-8")
    for line in text.splitlines():
        match = re.fullmatch(
            r"\s{2}([a-z][a-z0-9_]*):\s*\{approval:\s*(true|false)\}\s*",
            line,
        )
        if match:
            matrix[match.group(1)] = match.group(2) == "true"
    if not matrix:
        raise RuntimeError(f"No actions found in approval policy: {path}")
    return matrix


def action_requires_approval(action: str) -> bool:
    matrix = load_approval_matrix()
    if action not in matrix:
        raise ApprovalDeniedError(f"Unknown action is blocked by policy: {action}")
    return matrix[action]


def consume_action_approval(
    store,
    action: str,
    approval_id: str | None,
    scope: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Consume a matching one-time approval before a protected side effect."""
    if not action_requires_approval(action):
        return None
    if not approval_id:
        raise ApprovalRequiredError(f"Owner approval is required for action: {action}")
    try:
        return store.consume_approval_request(
            approval_id=approval_id,
            action=action,
            scope=scope or {},
        )
    except (KeyError, ValueError) as exc:
        raise ApprovalDeniedError(str(exc)) from exc
