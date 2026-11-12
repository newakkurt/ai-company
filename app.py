"""Cloud API and minimal dashboard for the 14-role AI Company."""
from __future__ import annotations

import asyncio
import hmac
import hashlib
import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from company.agents import agent_summary, load_agents
from company.mailbox import mail_status, run_mail_forever
from company.notifier import (
    notifier_configured,
    notify_cancellation,
    notify_sale,
    notify_unexpected_payment,
)
from company.scheduler import auto_tasks_enabled
from company.store import TaskStore
from company.worker import run_supervised, supervisor_status

ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
DB_PATH = Path(os.getenv("AI_COMPANY_DB_PATH", "/tmp/ai-company/company.db"))
store = TaskStore(DB_PATH)
app = FastAPI(title="New Akkurt AI Company", version="0.2.1")
app.mount("/assets", StaticFiles(directory=WEB_DIR), name="assets")

_worker_stop_event = threading.Event()
_worker_thread: threading.Thread | None = None
_worker_lock = threading.Lock()
_WORKER_POLL_SECONDS = 15

def worker_status() -> dict[str, Any]:
    enabled = os.getenv("AI_COMPANY_EMBEDDED_WORKER", "").strip().lower() == "true"
    running = bool(_worker_thread and _worker_thread.is_alive())
    return {
        "enabled": enabled,
        "running": running,
        "mode": "embedded_supabase_poll" if enabled else "disabled",
        "poll_seconds": _WORKER_POLL_SECONDS,
        **supervisor_status(),
    }


@app.on_event("startup")
def start_embedded_worker() -> None:
    global _worker_thread
    if os.getenv("AI_COMPANY_EMBEDDED_WORKER", "").strip().lower() != "true":
        return
    with _worker_lock:
        if _worker_thread and _worker_thread.is_alive():
            return
        missing = [key for key in (
            "SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_DB_GATE_KEY"
        ) if not os.getenv(key)]
        if not (os.getenv("GEMINI_API_KEY") or os.getenv("GROQ_API_KEY")):
            missing.append("GEMINI_API_KEY or GROQ_API_KEY")
        if missing:
            print("agent_worker: startup blocked; missing environment keys: " + ", ".join(missing), flush=True)
            return
        _worker_stop_event.clear()
        _worker_thread = threading.Thread(
            target=run_supervised,
            kwargs={"stop_event": _worker_stop_event, "poll_seconds": _WORKER_POLL_SECONDS},
            name="ai-company-agent-worker",
            daemon=True,
        )
        _worker_thread.start()
        print("agent_worker: embedded worker started; analysis_only=true", flush=True)


@app.on_event("shutdown")
def stop_embedded_worker() -> None:
    _worker_stop_event.set()
    thread = _worker_thread
    if thread and thread.is_alive():
        thread.join(timeout=25)
    print("agent_worker: embedded worker shutdown requested", flush=True)


# --- Optional embedded services: owner mailbox loop and Telegram intake -------------
_services_stop_event = threading.Event()
_service_threads: dict[str, threading.Thread] = {}


def _flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() == "true"


def _run_telegram_intake(stop_event: threading.Event) -> None:
    from company.telegram import TelegramIntake
    try:
        TelegramIntake().poll_forever(stop_event=stop_event)
    except ValueError as exc:  # missing token / allow-list
        print(f"telegram: intake not started: {exc}", flush=True)


@app.on_event("startup")
def start_embedded_services() -> None:
    _services_stop_event.clear()
    targets = {
        "mail": (_flag("AI_COMPANY_EMBEDDED_MAIL"),
                 lambda: run_mail_forever(stop_event=_services_stop_event)),
        "telegram": (_flag("AI_COMPANY_EMBEDDED_TELEGRAM"),
                     lambda: _run_telegram_intake(_services_stop_event)),
    }
    for name, (enabled, target) in targets.items():
        existing = _service_threads.get(name)
        if not enabled or (existing and existing.is_alive()):
            continue
        thread = threading.Thread(target=target, name=f"ai-company-{name}", daemon=True)
        _service_threads[name] = thread
        thread.start()


@app.on_event("shutdown")
def stop_embedded_services() -> None:
    _services_stop_event.set()
    for thread in _service_threads.values():
        if thread.is_alive():
            thread.join(timeout=10)


def services_status() -> dict[str, Any]:
    return {
        "scheduler": {"enabled": auto_tasks_enabled()},
        "notifier": {"configured": notifier_configured()},
        "mail": {**mail_status(), "running": bool(
            _service_threads.get("mail") and _service_threads["mail"].is_alive())},
        "telegram": {"enabled": _flag("AI_COMPANY_EMBEDDED_TELEGRAM"), "running": bool(
            _service_threads.get("telegram") and _service_threads["telegram"].is_alive())},
    }


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
    gemini_configured = bool(os.getenv("GEMINI_API_KEY"))
    groq_configured = bool(os.getenv("GROQ_API_KEY"))
    return {
        "gemini": gemini_configured,
        "groq": groq_configured,
        "ollama": False,
        "model": os.getenv("AI_COMPANY_GEMINI_MODEL", "gemini-3.5-flash-lite"),
        "fallback_model": os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
        "ready": gemini_configured or groq_configured,
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
    worker = worker_status()
    worker_ready = not worker["enabled"] or worker["running"]
    return {
        "ok": True,
        "ready": bool(provider["ready"] and database["connected"] and worker_ready),
        "service": "ai-company",
        "agents": len(load_agents()),
        "provider": provider,
        "database": database,
        "worker": worker,
        "services": services_status(),
        "mode": "analysis_only",
        "external_actions_enabled": False,
    }


@app.api_route("/", methods=["GET", "HEAD"])
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
        "worker": worker_status(),
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
    return item


@app.post("/api/tasks", dependencies=[Depends(require_api_key)])
def create_task(payload: TaskInput):
    item = store.create_task(payload.description)
    store.assign_agents(item["task_id"], [agent.id for agent in load_agents()])
    return {"task_id": item["task_id"], "status": "planned", "assigned_agents": len(load_agents())}


@app.post("/api/tasks/{task_id}/run", dependencies=[Depends(require_api_key)])
def start_analysis(task_id: str):
    item = store.get_task(task_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if not provider_status()["ready"]:
        raise HTTPException(status_code=503, detail="No AI provider (GEMINI_API_KEY / GROQ_API_KEY) is configured.")
    if item["status"] == "running":
        return {"task_id": task_id, "status": "running"}
    if item["status"] == "completed":
        return {"task_id": task_id, "status": "completed"}
    if item["status"] == "failed":
        raise HTTPException(status_code=409, detail="Task failed; inspect persisted events before retrying.")
    return {"task_id": task_id, "status": "queued", "worker": worker_status()}


@app.get("/api/tasks/{task_id}/run-status", dependencies=[Depends(require_api_key)])
def analysis_status(task_id: str):
    item = store.get_task(task_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "task_id": task_id,
        "status": item["status"],
        "output_count": len(item.get("agent_outputs", [])),
        "worker": worker_status(),
    }


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
async def buymeacoffee_webhook(request: Request,
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
        await asyncio.to_thread(notify_unexpected_payment, event_type, "desteklenmeyen olay türü", data)
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
        if existing:
            await asyncio.to_thread(notify_cancellation, safe_subscription_id, status)
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
        await asyncio.to_thread(
            notify_unexpected_payment, event_type,
            "plan/fiyat/para birimi yapılandırılmış NetCmd PRO ile eşleşmiyor", data,
        )
        return {"ok": True, "ignored": "not_the_configured_netcmd_pro_plan"}
    if str(data.get("status", "active")).lower() not in {"active", "succeeded"}:
        store.record_payment_event(event_key, event_type, subscription_id)
        await asyncio.to_thread(
            notify_unexpected_payment, event_type, "üyelik durumu aktif değil", data,
        )
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
    # After the event is recorded: a failed notification must not trigger provider retries.
    await asyncio.to_thread(notify_sale, event_type, membership)

    return {"ok": True, "membership_status": "active", "task_id": task_id,
            "assigned_agents": len(load_agents())}


@app.get("/api/health", dependencies=[Depends(require_api_key)])
def private_health():
    return {"ok": True, "provider": provider_status(), "agent_count": len(load_agents()), "worker": worker_status()}

# --- Digital product factory ---------------------------------------------------------
from fastapi.responses import FileResponse as DownloadFileResponse
from company.product_factory import (
    build_product, create_research_task, product_metadata, product_zip_path, score_idea,
)


class ProductResearchInput(BaseModel):
    description: str = Field(min_length=20, max_length=4000)


class ProductScoreInput(BaseModel):
    problem_urgency: int = Field(default=3, ge=1, le=5)
    willingness_to_pay: int = Field(default=3, ge=1, le=5)
    market_access: int = Field(default=3, ge=1, le=5)
    feasibility: int = Field(default=3, ge=1, le=5)
    differentiation: int = Field(default=3, ge=1, le=5)
    time_to_revenue: int = Field(default=3, ge=1, le=5)
    supportability: int = Field(default=3, ge=1, le=5)
    security_risk: int = Field(default=1, ge=1, le=5)


class ProductBuildInput(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    description: str = Field(min_length=20, max_length=4000)
    product_type: str = Field(default="python_api", pattern="^(python_api|web_app|python_cli)$")
    version: str = Field(default="0.1.0", pattern="^\\d+\\.\\d+\\.\\d+$")


@app.get("/api/factory/status", dependencies=[Depends(require_api_key)])
def product_factory_status():
    return {
        "enabled": True,
        "pipeline": ["market_research", "problem_discovery", "weighted_scoring",
                     "product_generation", "documentation", "sample_data", "static_qa",
                     "security_scan", "versioned_zip", "checksum", "backup_copy"],
        "generation_requires_provider": provider_status()["ready"],
        "source_execution": False,
        "release_status": "review_required",
    }


@app.post("/api/factory/research", dependencies=[Depends(require_api_key)])
def product_factory_research(payload: ProductResearchInput):
    return create_research_task(payload.description, store=store)


@app.post("/api/factory/score", dependencies=[Depends(require_api_key)])
def product_factory_score(payload: ProductScoreInput):
    return score_idea(payload.model_dump())


@app.post("/api/factory/build", dependencies=[Depends(require_api_key)])
def product_factory_build(payload: ProductBuildInput):
    if not provider_status()["ready"]:
        raise HTTPException(status_code=503, detail="No AI provider is configured.")
    try:
        return build_product(payload.name, payload.description,
                             payload.product_type, payload.version)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/factory/products/{product_id}", dependencies=[Depends(require_api_key)])
def product_factory_detail(product_id: str):
    try:
        return product_metadata(product_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Product release not found.")


@app.get("/api/factory/products/{product_id}/download", dependencies=[Depends(require_api_key)])
def product_factory_download(product_id: str):
    try:
        path = product_zip_path(product_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Product ZIP not found.")
    return DownloadFileResponse(path, media_type="application/zip", filename=path.name)
