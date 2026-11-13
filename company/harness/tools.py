"""Light local tools (read / write / edit / bash) for small agents (principles 3-5).

Everything is sandboxed to a root directory, size-bounded and returns plain dicts so a
small model can consume the result. Shell is OFF unless AI_COMPANY_ALLOW_SHELL=true and
every command passes safety.check_command; commands that need approval are queued for a
human instead of being run.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from . import safety
from .escalation import HumanReviewQueue, verify_output
from .privacy import redact

MAX_READ_BYTES = 200_000
MAX_WRITE_BYTES = 500_000
MAX_OUTPUT_CHARS = 8_000
SAFE_ENV_KEYS = ("PATH", "LANG", "LC_ALL", "TZ")


class ToolError(Exception):
    pass


def _truncate(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    return text if len(text) <= limit else text[:limit] + f"\n…[truncated {len(text) - limit} chars]"


class ToolBox:
    def __init__(self, root: Path | str, review_queue: HumanReviewQueue | None = None,
                 allow_shell: bool | None = None, approver=None, task_id: str = "adhoc"):
        self.root = Path(root).resolve()
        self.queue = review_queue
        self.task_id = task_id
        self.approver = approver  # callable(command, verdict) -> bool, e.g. checks a one-time approval
        self.allow_shell = (os.getenv("AI_COMPANY_ALLOW_SHELL", "false").lower() == "true"
                            if allow_shell is None else allow_shell)

    # -- file tools -----------------------------------------------------------
    def read_file(self, path: str, offset: int = 0, limit: int = 400) -> dict:
        target = safety.resolve_in_sandbox(path, self.root)
        if not target.is_file():
            raise ToolError("not a file")
        if target.stat().st_size > MAX_READ_BYTES:
            raise ToolError(f"file larger than {MAX_READ_BYTES} bytes; read a slice with shell tools")
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        chunk = lines[max(0, offset):max(0, offset) + max(1, min(limit, 2000))]
        text, findings = redact("\n".join(f"{i + offset + 1}\t{line}" for i, line in enumerate(chunk)))
        return {"status": "ok", "path": str(target.relative_to(self.root)), "total_lines": len(lines),
                "content": _truncate(text), "redacted": [f.kind for f in findings]}

    def write_file(self, path: str, content: str, overwrite: bool = False) -> dict:
        target = safety.resolve_in_sandbox(path, self.root, for_write=True)
        if len(content.encode("utf-8")) > MAX_WRITE_BYTES:
            raise ToolError("content too large")
        check = verify_output(content, forbid_secrets=True)
        if not check.ok:
            raise ToolError("write blocked by verification: " + ",".join(check.reasons))
        if target.exists() and not overwrite:
            raise ToolError("file exists; pass overwrite=true")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {"status": "ok", "path": str(target.relative_to(self.root)), "bytes": len(content.encode())}

    def edit_file(self, path: str, old: str, new: str) -> dict:
        target = safety.resolve_in_sandbox(path, self.root, for_write=True)
        if not target.is_file():
            raise ToolError("not a file")
        text = target.read_text(encoding="utf-8")
        if not old or text.count(old) != 1:
            raise ToolError(f"'old' must match exactly once (found {text.count(old) if old else 0})")
        updated = text.replace(old, new, 1)
        if not verify_output(new, forbid_secrets=True, min_chars=0).ok:
            raise ToolError("edit blocked by verification: secret-like content")
        target.write_text(updated, encoding="utf-8")
        return {"status": "ok", "path": str(target.relative_to(self.root))}

    # -- shell ------------------------------------------------------------------
    def run_bash(self, command: str, timeout: int = 60) -> dict:
        if not self.allow_shell:
            return {"status": "disabled", "reason": "shell is off (AI_COMPANY_ALLOW_SHELL=false)"}
        verdict = safety.check_command(command)
        if verdict.level == safety.DENY:
            return {"status": "denied", "reasons": verdict.reasons}
        if verdict.level == safety.NEEDS_APPROVAL:
            if not (self.approver and self.approver(command, verdict)):
                review_id = None
                if self.queue is not None:
                    review_id = self.queue.enqueue(self.task_id, "shell_command_needs_approval",
                                                   {"command": command[:500], "reasons": verdict.reasons},
                                                   ["shell"], 0)
                return {"status": "approval_required", "reasons": verdict.reasons, "review_id": review_id}
        env = {k: os.environ[k] for k in SAFE_ENV_KEYS if k in os.environ}
        env["HOME"] = str(self.root)
        try:
            done = subprocess.run(["bash", "-c", command], cwd=self.root, env=env, capture_output=True,
                                  text=True, timeout=max(1, min(timeout, 300)))
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "timeout": timeout}
        out, findings = redact((done.stdout or "") + (("\n[stderr]\n" + done.stderr) if done.stderr else ""))
        return {"status": "ok" if done.returncode == 0 else "error", "returncode": done.returncode,
                "output": _truncate(out), "redacted": [f.kind for f in findings]}

    # -- dispatch ---------------------------------------------------------------
    TOOLS = ("read_file", "write_file", "edit_file", "run_bash")

    def call(self, name: str, args: dict | None = None) -> dict:
        """Single entry point for a model's tool call; never raises."""
        if name not in self.TOOLS:
            return {"status": "error", "error": f"unknown tool: {name}"}
        try:
            return getattr(self, name)(**(args or {}))
        except (ToolError, safety.PathViolation) as exc:
            return {"status": "error", "error": str(exc)}
        except TypeError:
            return {"status": "error", "error": "invalid arguments"}
        except OSError as exc:
            return {"status": "error", "error": type(exc).__name__}
