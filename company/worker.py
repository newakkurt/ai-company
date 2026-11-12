"""Durable, analysis-only task consumer for Supabase-backed agent work."""
import argparse
import os
import signal
import sys
import threading
import time

from .agent_runner import run_task
from .notifier import notify_task_failed, notify_task_result
from .scheduler import seed_due_tasks
from .store import TaskStore

REQUIRED_ENV = (
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_DB_GATE_KEY",
)
SEED_INTERVAL_SECONDS = 300


def _safe_notify(func, *args):
    """Notifications are best-effort and must never change a task's outcome."""
    try:
        func(*args)
    except Exception as exc:  # noqa: BLE001
        print(f"agent_worker: notify failed; error_type={type(exc).__name__}", flush=True)


def process_one_task(store=None, provider=None):
    """Claim and execute at most one dry-run task, persisting every agent result."""
    store = store or TaskStore()
    task_id = store.claim_next_task()
    if not task_id:
        return {"status": "idle"}

    print(f"agent_worker: claimed task {task_id}", flush=True)
    try:
        results = run_task(task_id, store=store, provider=provider)
        store.complete_task(task_id, output_count=len(results))
        print(
            f"agent_worker: completed task {task_id}; "
            f"persisted_outputs={len(results)}",
            flush=True,
        )
        if task_id.startswith("auto-"):
            _safe_notify(lambda: notify_task_result(store.get_task(task_id)))
        return {
            "status": "completed",
            "task_id": task_id,
            "output_count": len(results),
        }
    except Exception as exc:
        # Only log the exception class. Never emit provider responses or credentials.
        try:
            store.fail_task(
                task_id,
                error_type=type(exc).__name__,
                error_summary=str(exc) if type(exc).__name__ == "GeminiAPIError" else None,
            )
        finally:
            print(
                f"agent_worker: failed task {task_id}; "
                f"error_type={type(exc).__name__}",
                file=sys.stderr,
                flush=True,
            )
        _safe_notify(notify_task_failed, task_id, type(exc).__name__)
        return {
            "status": "failed",
            "task_id": task_id,
            "error_type": type(exc).__name__,
        }


def run_forever(stop_event=None, poll_seconds: int = 15):
    """Poll the durable queue until a shutdown event is received."""
    stop_event = stop_event or threading.Event()
    print("agent_worker: polling Supabase queue; analysis_only=true", flush=True)
    store = TaskStore()
    last_seed = 0.0
    while not stop_event.is_set():
        if time.monotonic() - last_seed >= SEED_INTERVAL_SECONDS:
            last_seed = time.monotonic()
            try:
                seed_due_tasks(store)  # idempotent; creates today's autonomous work
            except Exception as exc:  # noqa: BLE001 - a scheduler bug must not stop the queue
                print(f"agent_worker: scheduler failed; error_type={type(exc).__name__}",
                      file=sys.stderr, flush=True)
        try:
            result = process_one_task(store=store)
            if result["status"] in {"idle", "failed"}:
                stop_event.wait(poll_seconds)
        except Exception as exc:
            print(
                f"agent_worker: queue poll failed; error_type={type(exc).__name__}",
                file=sys.stderr,
                flush=True,
            )
            stop_event.wait(poll_seconds)
    print("agent_worker: shutdown complete", flush=True)


def validate_environment():
    missing = [name for name in REQUIRED_ENV if not os.getenv(name)]
    if not (os.getenv("GEMINI_API_KEY") or os.getenv("GROQ_API_KEY")):
        missing.append("GEMINI_API_KEY or GROQ_API_KEY")
    if missing:
        raise RuntimeError("Missing required worker secrets: " + ", ".join(missing))


def main():
    parser = argparse.ArgumentParser(description="AI Company durable analysis worker")
    parser.add_argument("--once", action="store_true", help="process one queued task and exit")
    parser.add_argument("--poll-seconds", type=int, default=15)
    args = parser.parse_args()

    validate_environment()
    if args.poll_seconds < 5:
        parser.error("--poll-seconds must be at least 5")

    if args.once:
        store = TaskStore()
        try:
            seed_due_tasks(store)
        except Exception as exc:  # noqa: BLE001
            print(f"agent_worker: scheduler failed; error_type={type(exc).__name__}", file=sys.stderr, flush=True)
        result = process_one_task(store=store)
        return 1 if result["status"] == "failed" else 0

    stop_event = threading.Event()

    def request_shutdown(signum, frame):
        stop_event.set()

    signal.signal(signal.SIGTERM, request_shutdown)
    signal.signal(signal.SIGINT, request_shutdown)
    run_forever(stop_event=stop_event, poll_seconds=args.poll_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
