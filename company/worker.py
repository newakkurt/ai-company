"""Durable, analysis-only task consumer for Supabase-backed agent work."""
import argparse
import os
import signal
import sys
import time

from .agent_runner import run_task
from .store import TaskStore

REQUIRED_ENV = (
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_DB_GATE_KEY",
    "GEMINI_API_KEY",
)


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
        return {
            "status": "completed",
            "task_id": task_id,
            "output_count": len(results),
        }
    except Exception as exc:
        # Only log the exception class. Never emit provider responses or credentials.
        try:
            store.fail_task(task_id, error_type=type(exc).__name__)
        finally:
            print(
                f"agent_worker: failed task {task_id}; "
                f"error_type={type(exc).__name__}",
                file=sys.stderr,
                flush=True,
            )
        return {
            "status": "failed",
            "task_id": task_id,
            "error_type": type(exc).__name__,
        }


def validate_environment():
    missing = [name for name in REQUIRED_ENV if not os.getenv(name)]
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
        result = process_one_task()
        return 1 if result["status"] == "failed" else 0

    stopping = False

    def request_shutdown(signum, frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, request_shutdown)
    signal.signal(signal.SIGINT, request_shutdown)

    print("agent_worker: polling Supabase queue; analysis_only=true", flush=True)
    while not stopping:
        try:
            result = process_one_task()
            if result["status"] == "idle":
                time.sleep(args.poll_seconds)
        except Exception as exc:
            print(
                f"agent_worker: queue poll failed; error_type={type(exc).__name__}",
                file=sys.stderr,
                flush=True,
            )
            time.sleep(args.poll_seconds)
    print("agent_worker: shutdown complete", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
