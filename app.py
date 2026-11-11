"""Cloud API and minimal dashboard for the 14-role AI Company."""
from __future__ import annotations

import hmac
import hashlib
import json
import os
import re
import threading
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from company.agents import agent_summary, load_agents
from company.store import TaskStore
from company.agent_runner import run_task

ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
DB_PATH = Path(os.getenv("AI_COMPANY_DB_PATH", "/tmp/ai-company/company.db"))
store = TaskStore(DB_PATH)
app = FastAPI(title="New Akkurt AI Company", version="0.2.1")
app.mount("/assets", StaticFiles(directory=WEB_DIR), name="assets")

_run_lock = threading.Lock()
_run_state: dict[str, dict[str, Any]] = {}


class TaskInput(BaseModel):
    description: str = Field(min_length=5, max_length=4000)


def require_api_key(authorization: str | None = Header(default=None)) -> None:
    expected = os.getenv("AI_COMPANY_API_KEY", "")
    if not expected:
        raise HTTPException(status_code=503, detail="AI Company API key is not configured on the server")
    supplied = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Invalid API key")


def provider_status() -> dict[str, Any]:
    configured = bool(os.getenv("GEMINI_API_KEY"))
    return {
        "gemini": configured,
        "ollama": False,
        "model": os.getenv("AI_COMPANY_GEMINI_MODEL", "gemini-3.8-flash"),
        "ready": configured,
    }


def database_status() -> dict[str, Any]:
    required = ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_DB_GATE_KEY")
    configured = {key: bool(os.getenv(key)) for key in required}
    backend = "supabase" if all(configured.values()) else "sqlite_ephemeral"
    try:
        store.list_tasks(limit=1)
        return {"backend": backend, "connected": True, "configured": configured, "error": None}
    except Exception as exc:  # expose safe diagnostic text, never credentials
        message = str(exc)
        safe_message = message[:240] if message else type(exc).__name__
        for key in required + ("GEMINI_API_KEY",):
            secret = os.getenv(key, "")
            if secret:
                safe_message = safe_message.replace(secret, "[redacted]")
        return {
            "backend": backend,
            "connected": False,
            "configured": configured,
            "error": safe_message,
        }


@app.get("/healthz")
def healthz():
    return {"ok": True, "service": "ai-company", "agents": len(load_agents())}


@app.get("/readyz")
def readiness():
    provider = provider_status()
    database = database_status()
    return {
        "ok": True,
        "ready": bool(provider["ready"] and database["connected"]),
        "service": "ai-company",
        "agents": len(load_agents()),
        "provider": provider,
        "database": database,
        "mode": "analysis_only",
        "external_actions_enabled": False,
    }


@app.get("/")
def storefront():
    return FileResponse(WEB_DIR / "sales.html")


@app.get("/sales")
def sales_page():
    return FileResponse(WEB_DIR / "sales.html")


@app.get("/admin")
def dashboard():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/checkout")
def checkout():
    target = os.getenv("BMC_PRO_CHECKOUT_URL", "https://buymeacoffee.com/sevketkaynar").strip()
    if not target.startswith("https://buymeacoffee.com/"):
        raise HTTPException(status_code=503, detail="Secure checkout URL is not configured.")
    return RedirectResponse(target, status_code=303)


@app.get("/api/status", dependencies=[Depends(require_api_key)])
def status():
    return {
        "service": "New Akkurt AI Company",
        "agents": len(load_agents()),
        "provider": provider_status(),
        "mode": "analysis_only",
        "external_actions_enabled": False,
        "database": database_status(),
    }


@app.get("/api/agents", dependencies=[Depends(require_api_key)])
def agents():
    return {"agents": agent_summary()}


@app.get("/api/tasks", dependencies=[Depends(require_api_key)])
def tasks():
    return {"tasks": store.list_tasks(limit=50)}


@app.get("/api/tasks/{task_id}", dependencies=[Depends(require_api_key)])
def task_detail(task_id: str):
    item = store.get_task(task_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Task not found")
    item["run_state"] = _run_state.get(task_id, {"status": "not_started"})
    return item


@app.post("/api/tasks", dependencies=[Depends(require_api_key)])
def create_task(payload: TaskInput):
    item = store.create_task(payload.description)
    store.assign_agents(item["task_id"], [agent.id for agent in load_agents()])
    return {"task_id": item["task_id"], "status": "planned", "assigned_agents": len(load_agents())}


def _execute_analysis(task_id: str) -> None:
    state = _run_state.setdefault(task_id, {})
    state.update(status="queued", message="Waiting for the analysis worker.")
    _run_lock.acquire()
    try:
        state.update(status="running", message="14 role agents are preparing analysis with Gemini 3.8 Flash.")
        results = run_task(task_id, store=store)
        state.update(status="completed", result_count=len(results), message="Analysis saved.")
    except Exception as exc:
        state.update(status="failed", message=f"Analysis failed: {type(exc).__name__}")
    finally:
        _run_lock.release()


@app.post("/api/tasks/{task_id}/run", dependencies=[Depends(require_api_key)])
def start_analysis(task_id: str, background: BackgroundTasks):
    item = store.get_task(task_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if not provider_status()["ready"]:
        raise HTTPException(status_code=503, detail="Gemini 3.8 Flash is not configured.")
    current = _run_state.get(task_id, {}).get("status")
    if current == "running":
        return {"task_id": task_id, "status": "running"}
    _run_state[task_id] = {"status": "queued"}
    background.add_task(_execute_analysis, task_id)
    return {"task_id": task_id, "status": "queued"}


@app.get("/api/tasks/{task_id}/run-status", dependencies=[Depends(require_api_key)])
def analysis_status(task_id: str):
    if store.get_task(task_id) is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return _run_state.get(task_id, {"status": "not_started"})


def _verify_bmc_signature(raw_body: bytes, secret: str, signature: str) -> bool:
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.strip().lower())


def _iso_timestamp(value: Any) -> str | None:
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat() if value else None
    except (TypeError, ValueError, OverflowError):
        return None


@app.post("/webhooks/buymeacoffee")
async def buymeacoffee_webhook(request: Request, background: BackgroundTasks,
                               signature: str | None = Header(default=None, alias="x-signature-sha256")):
    secret = os.getenv("BMC_WEBHOOK_SECRET", "")
    if not secret:
        raise HTTPException(status_code=503, detail="Buy Me a Coffee webhook is not configured.")
    raw_body = await request.body()
    if not _verify_bmc_signature(raw_body, secret, signature or ""):
        raise HTTPException(status_code=401, detail="Invalid webhook signature.")
    try:
        event = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    event_id = str(event.get("event_id", "")).strip()
    event_type = str(event.get("type", "")).strip()
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    if not event_id or not event_type:
        raise HTTPException(status_code=400, detail="Missing event_id or type.")
    if event.get("live_mode") is not True:
        return {"ok": True, "ignored": "test_event"}
    event_key = f"bmc-{event_id}"
    if store.get_payment_event(event_key):
        return {"ok": True, "duplicate": True}

    supported = {"membership.started", "membership.updated", "membership.cancelled", "membership.paused"}
    if event_type not in supported:
        store.record_payment_event(event_key, event_type, None)
        return {"ok": True, "ignored": "unsupported_event"}

    subscription_id = str(data.get("id") or data.get("psp_id") or "").strip()
    if not subscription_id or len(subscription_id) > 120:
        raise HTTPException(status_code=400, detail="Missing or invalid subscription identifier.")
    safe_subscription_id = re.sub(r"[^A-Za-z0-9_-]", "-", subscription_id)[:100]
    task_id = f"bmc-sub-{safe_subscription_id}"
    existing = store.get_membership(subscription_id)

    if event_type in {"membership.cancelled", "membership.paused"}:
        if existing:
            status = "canceled" if event_type.endswith("cancelled") else "paused"
            updated = {**existing, "status": status, "updated_at": datetime.now(timezone.utc).isoformat()}
            store.upsert_membership(updated)
        store.record_payment_event(event_key, event_type, subscription_id)
        return {"ok": True, "membership_status": "updated" if existing else "not_found"}

    expected_level = os.getenv("BMC_PRO_MEMBERSHIP_LEVEL_ID", "").strip()
    if not expected_level:
        raise HTTPException(status_code=503, detail="PRO membership level ID is not configured.")
    try:
        level_id = int(data.get("membership_level_id", -1))
        expected_price = Decimal(os.getenv("BMC_PRO_PRICE_USD", "69"))
        amount = Decimal(str(data.get("amount", "0")))
    except (ValueError, InvalidOperation):
        raise HTTPException(status_code=400, detail="Invalid membership price or level.")
    currency = str(data.get("currency", "")).upper()
    if level_id != int(expected_level) or currency != "USD" or amount != expected_price:
        store.record_payment_event(event_key, event_type, subscription_id)
        return {"ok": True, "ignored": "not_the_configured_netcmd_pro_plan"}
    if str(data.get("status", "active")).lower() not in {"active", "succeeded"}:
        store.record_payment_event(event_key, event_type, subscription_id)
        return {"ok": True, "ignored": "membership_not_active"}

    task = store.create_task(
        "Paid NetCmd PRO customer onboarding: prepare a safe, evidence-led network audit workflow. "
        "No customer credentials, direct device access, configuration changes, or external actions are permitted.",
        task_id=task_id,
    )
    store.assign_agents(task_id, [agent.id for agent in load_agents()])
    membership = {
        "subscription_id": subscription_id,
        "supporter_email": data.get("supporter_email"),
        "supporter_name": data.get("supporter_name"),
        "membership_level_id": level_id,
        "membership_level_name": data.get("membership_level_name"),
        "amount": float(amount),
        "currency": currency,
        "status": "active",
        "current_period_end": _iso_timestamp(data.get("current_period_end")),
        "task_id": task_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    store.upsert_membership(membership)
    store.record_payment_event(event_key, event_type, subscription_id)

    if event_type == "membership.started" and not task.get("agent_outputs"):
        background.add_task(_execute_analysis, task_id)
    return {"ok": True, "membership_status": "active", "task_id": task_id,
            "assigned_agents": len(load_agents())}


@app.get("/api/health", dependencies=[Depends(require_api_key)])
def private_health():
    return {"ok": True, "provider": provider_status(), "agent_count": len(load_agents())}
