"""Durable, analysis-only task consumer for Supabase-backed agent work."""
import argparse
import json
import re
import os
import signal
import sys
import threading
import time
from datetime import datetime, timedelta, timezone

from .agent_runner import run_task
from .llm import get_provider
from .product_factory import build_product
from .crm import upsert_company as crm_upsert_company
from .source_verification import verify_public_source
from .notifier import notify_owner, notify_task_failed, notify_task_result
from .scheduler import seed_due_tasks
from .store import TaskStore
from .harness.state_machine import safe_record
from .harness.routing import PrivacyRoutingError

REQUIRED_ENV = (
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_DB_GATE_KEY",
)
SEED_INTERVAL_SECONDS = 300

_SUPERVISOR_STATE = {"restart_count": 0, "last_restart_at": None, "last_error_type": None}


def supervisor_status():
    """Safe operational counters for the hosted readiness endpoint."""
    return dict(_SUPERVISOR_STATE)


def run_supervised(stop_event=None, poll_seconds: int = 15,
                   initial_backoff_seconds: int = 5,
                   max_backoff_seconds: int = 120):
    """Keep the durable queue consumer alive after unexpected worker-loop exits."""
    stop_event = stop_event or threading.Event()
    backoff = max(1, initial_backoff_seconds)
    while not stop_event.is_set():
        try:
            run_forever(stop_event=stop_event, poll_seconds=poll_seconds)
            if stop_event.is_set():
                break
            raise RuntimeError("worker_loop_exited_unexpectedly")
        except Exception as exc:  # noqa: BLE001 - supervisor must survive worker failures
            _SUPERVISOR_STATE["restart_count"] += 1
            _SUPERVISOR_STATE["last_restart_at"] = time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
            )
            _SUPERVISOR_STATE["last_error_type"] = type(exc).__name__
            print(
                "agent_worker: supervisor restarting worker loop; "
                f"restart_count={_SUPERVISOR_STATE['restart_count']} "
                f"error_type={type(exc).__name__} backoff_seconds={backoff}",
                file=sys.stderr, flush=True,
            )
            stop_event.wait(backoff)
            backoff = min(max_backoff_seconds, backoff * 2)


def _escalate_to_human(task_id: str, reason: str, error_type: str):
    """Put work automation must not decide alone into the SQLite human review queue."""
    try:
        from .harness.escalation import HumanReviewQueue
        review_id = HumanReviewQueue().enqueue(task_id, reason, {"error_type": error_type})
        safe_record(task_id, "failed", "escalated", reason, review_id=review_id)
        print(f"agent_worker: escalated to human; task_id={task_id}; review_id={review_id}", flush=True)
    except Exception as exc:  # noqa: BLE001 - escalation is best-effort and must not mask the failure
        print(f"agent_worker: escalation failed; error_type={type(exc).__name__}", flush=True)


def _safe_notify(func, *args):
    """Notifications are best-effort and must never change a task's outcome."""
    try:
        func(*args)
    except Exception as exc:  # noqa: BLE001
        print(f"agent_worker: notify failed; error_type={type(exc).__name__}", flush=True)


def notify_due_followups(store=None, now=None):
    """Send owner-only reminders for due CRM follow-ups; never contact prospects."""
    store = store or TaskStore()
    now = now or datetime.now(timezone.utc)
    rows = store._request("crm_followups", params={
        "select":"*", "status":"eq.pending", "due_at":f"lte.{now.isoformat()}", "limit":"100"
    })
    sent = 0
    cutoff = now - timedelta(days=1)
    for row in rows:
        last = row.get("last_notified_at")
        if last:
            try:
                last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
                if last_dt >= cutoff:
                    continue
            except (TypeError, ValueError):
                pass
        message = (
            "⏰ CRM takip zamanı geldi.\n"
            f"Şirket kaydı: {row.get('company_id','—')}\n"
            f"Not: {row.get('note') or 'Planlanan müşteri takibi'}\n"
            f"Takip kaydı: {row.get('followup_id')}"
        )
        if notify_owner(message):
            store._request("crm_followups", "PATCH",
                           {"followup_id":f"eq.{row['followup_id']}"},
                           {"last_notified_at":now.isoformat()}, "return=minimal")
            sent += 1
    return sent


def _start_task_heartbeat(store, task_id: str, interval_seconds: int = 60):
    """Refresh the task's quiet lease while a long LLM run is still active."""
    heartbeat = getattr(store, "heartbeat_task", None)
    if not callable(heartbeat):
        return None, None
    stop_event = threading.Event()

    def run():
        while not stop_event.wait(interval_seconds):
            try:
                if not heartbeat(task_id):
                    print(f"agent_worker: task lease no longer owned; task_id={task_id}", flush=True)
                    return
            except Exception as exc:  # noqa: BLE001 - heartbeat failures are visible but isolated
                print(f"agent_worker: heartbeat failed; task_id={task_id}; error_type={type(exc).__name__}",
                      file=sys.stderr, flush=True)

    thread = threading.Thread(
        target=run, name=f"ai-company-heartbeat-{task_id}", daemon=True
    )
    thread.start()
    return stop_event, thread


def process_one_task(store=None, provider=None):
    """Claim and execute at most one dry-run task, persisting every agent result."""
    store = store or TaskStore()
    task_id = store.claim_next_task()
    if not task_id:
        return {"status": "idle"}

    print(f"agent_worker: claimed task {task_id}", flush=True)
    safe_record(task_id, "planned", "running", "worker_claim", mode="analysis_only")
    heartbeat_stop, heartbeat_thread = _start_task_heartbeat(store, task_id)
    try:
        results = run_task(task_id, store=store, provider=provider)
        # Save research leads only when the model emits the requested JSON block
        # and provides a public HTTPS source. Records remain unverified drafts.
        if task_id.startswith(("auto-prospects-", "crm-research-")):
            for item in results:
                output = item.get("output", "")
                match = re.search(r"CRM_LEADS_JSON\s*[:=]\s*(\[.*?\])", output, re.I | re.S)
                if not match:
                    continue
                try:
                    leads = json.loads(match.group(1))
                except (ValueError, TypeError):
                    continue
                if not isinstance(leads, list):
                    continue
                for lead in leads[:10]:
                    if not isinstance(lead, dict):
                        continue
                    source_url = str(lead.get("source_url", "")).strip()
                    if not source_url.startswith("https://") or "example.invalid" in source_url:
                        continue
                    if len(str(lead.get("company_name", "")).strip()) < 2:
                        continue
                    if len(str(lead.get("source_name", "")).strip()) < 2:
                        continue
                    verification = verify_public_source(source_url, str(lead.get("company_name", "")))
                    if verification["source_validation_status"] in {"unsafe_url", "unreachable", "too_large", "redirect_limit"}:
                        print("crm: prospect source rejected; status=" +
                              verification["source_validation_status"], flush=True)
                        continue
                    lead.update(verification)
                    lead["source_type"] = "agent_research_unverified"
                    try:
                        crm_upsert_company(lead, store=store)
                    except Exception as crm_exc:
                        print("crm: prospect ingest skipped; error_type=" +
                              type(crm_exc).__name__, file=sys.stderr, flush=True)
        if task_id.startswith("auto-digital-product-factory-"):
            research_context = "\n\n".join(
                f"[{item['agent_id']}]\n{item['output']}" for item in results
            )
            release = build_product(
                "Network Ops Starter",
                "Create the smallest useful offline-first network operations product "
                "for MSPs and IT teams. Use this week's specialist market/problem analysis "
                "to choose the most valuable narrow feature. Parse user-supplied sample/config "
                "text only; do not connect to devices, use credentials, or change infrastructure. "
                "Research and buyer context:\n" + research_context[:12000],
                product_type="python_api",
                version="0.1.0",
                provider=provider or get_provider(),
            )
            with open(release["download_path"], "rb") as artifact_file:
                store.save_product_release(release, artifact_file.read())
            store.record_agent_output(
                task_id, "product_factory",
                "Generated durable release metadata (source not executed):\n"
                + json.dumps({
                    k: v for k, v in release.items()
                    if k not in {"download_path", "checksum_path", "backup_path"}
                }, ensure_ascii=False, indent=2),
            )
            results.append({"agent_id": "product_factory", "output": json.dumps(release, ensure_ascii=False)})
        store.complete_task(task_id, output_count=len(results))
        safe_record(task_id, "running", "completed", "all_agents_saved", output_count=len(results))
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
        safe_record(task_id, "running", "failed", "exception", error_type=type(exc).__name__)
        if isinstance(exc, PrivacyRoutingError):
            _escalate_to_human(task_id, "privacy_routing_blocked", type(exc).__name__)
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
    finally:
        if heartbeat_stop:
            heartbeat_stop.set()
        if heartbeat_thread and heartbeat_thread.is_alive():
            heartbeat_thread.join(timeout=3)


def run_forever(stop_event=None, poll_seconds: int = 15):
    """Poll the durable queue until a shutdown event is received."""
    stop_event = stop_event or threading.Event()
    print("agent_worker: polling Supabase queue; analysis_only=true", flush=True)
    store = TaskStore()
    last_seed = 0.0
    last_followup_check = 0.0
    while not stop_event.is_set():
        if time.monotonic() - last_seed >= SEED_INTERVAL_SECONDS:
            last_seed = time.monotonic()
            try:
                seed_due_tasks(store)  # idempotent; creates today's autonomous work
            except Exception as exc:  # noqa: BLE001 - a scheduler bug must not stop the queue
                print(f"agent_worker: scheduler failed; error_type={type(exc).__name__}",
                      file=sys.stderr, flush=True)
        if time.monotonic() - last_followup_check >= 300:
            last_followup_check = time.monotonic()
            try:
                notify_due_followups(store=store)
            except Exception as exc:
                print(f"crm: follow-up reminder check failed; error_type={type(exc).__name__}",
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
