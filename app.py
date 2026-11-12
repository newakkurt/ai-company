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
    notify_owner,
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

@app.get("/payments")
def payments_dashboard():
    return FileResponse(WEB_DIR / "payments.html")


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
    if event_type.endswith(".refunded"):
        try:
            refund_amount = Decimal(str(data.get("amount", "0")))
            refund_currency = str(data.get("currency", "")).upper()
            if refund_amount <= 0 or not refund_currency:
                raise ValueError("missing refund amount/currency")
            refund_subscription = str(data.get("subscription_id") or data.get("psp_id") or "").strip() or None
            if hasattr(store, "_request"):
                inserted = store._request("payment_ledger", "POST", {"on_conflict":"event_id"}, {
                    "event_id":event_key,"event_type":event_type,"subscription_id":refund_subscription,
                    "product_code":"netcmd_pro","gross_amount":str(-refund_amount),
                    "currency":refund_currency,"platform_fee_amount":"0",
                    "processing_fee_estimate":"0","net_estimate":str(-refund_amount),
                    "entry_status":"refund_reported","provider_created_at":_iso_timestamp(event.get("created")),
                    "raw_event":event
                }, "resolution=ignore-duplicates,return=representation")
                first_refund_record = bool(inserted)
            else:
                with store._connect() as db:
                    db.execute("""CREATE TABLE IF NOT EXISTS payment_ledger (
                        event_id TEXT PRIMARY KEY,event_type TEXT NOT NULL,subscription_id TEXT,
                        product_code TEXT NOT NULL,gross_amount REAL NOT NULL,currency TEXT NOT NULL,
                        platform_fee_amount REAL NOT NULL,processing_fee_estimate REAL NOT NULL,
                        net_estimate REAL NOT NULL,entry_status TEXT NOT NULL,provider_created_at TEXT,
                        received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,raw_event TEXT NOT NULL)""")
                    cur=db.execute("""INSERT OR IGNORE INTO payment_ledger
                        (event_id,event_type,subscription_id,product_code,gross_amount,currency,
                         platform_fee_amount,processing_fee_estimate,net_estimate,entry_status,
                         provider_created_at,raw_event) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (event_key,event_type,refund_subscription,"netcmd_pro",float(-refund_amount),
                         refund_currency,0,0,float(-refund_amount),"refund_reported",
                         _iso_timestamp(event.get("created")),json.dumps(event)))
                    first_refund_record=cur.rowcount==1
            store.record_payment_event(event_key,event_type,refund_subscription)
            if first_refund_record:
                await asyncio.to_thread(notify_unexpected_payment,event_type,
                    "İade olayı kaydedildi; BMC panelindeki gerçek iade tutarı ve bakiyeyle mutabakat yapın",data)
            return {"ok":True,"refund_recorded":first_refund_record}
        except (ValueError, InvalidOperation):
            raise HTTPException(status_code=400,detail="Invalid refund amount or currency.")
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
    # Unique provider event ID is the financial ledger idempotency key.
    # The webhook event row remains the processing/audit record; ledger insertion
    # returns a row only for the first delivery, preventing duplicate sale alerts.
    gross = amount
    platform_fee = (gross * Decimal("0.05")).quantize(Decimal("0.01"))
    processing_fee = (gross * Decimal("0.034") + Decimal("0.30")).quantize(Decimal("0.01"))
    payout_fee_estimate = (gross * Decimal("0.005")).quantize(Decimal("0.01"))
    ledger_row = {
        "event_id": event_key, "event_type": event_type,
        "subscription_id": subscription_id, "product_code": "netcmd_pro",
        "gross_amount": str(gross), "currency": currency,
        "platform_fee_amount": str(platform_fee),
        "processing_fee_estimate": str(processing_fee),
        "net_estimate": str(gross - platform_fee - processing_fee - payout_fee_estimate),
        "entry_status": "recognized_estimate",
        "provider_created_at": _iso_timestamp(event.get("created")),
        "raw_event": event,
    }
    try:
        if hasattr(store, "_request"):
            inserted = store._request(
                "payment_ledger", "POST", {"on_conflict": "event_id"}, ledger_row,
                "resolution=ignore-duplicates,return=representation"
            )
            first_financial_record = bool(inserted)
        else:
            with store._connect() as db:
                db.execute("""CREATE TABLE IF NOT EXISTS payment_ledger (
                    event_id TEXT PRIMARY KEY,event_type TEXT NOT NULL,subscription_id TEXT,
                    product_code TEXT NOT NULL,gross_amount REAL NOT NULL,currency TEXT NOT NULL,
                    platform_fee_amount REAL NOT NULL,processing_fee_estimate REAL NOT NULL,
                    net_estimate REAL NOT NULL,entry_status TEXT NOT NULL,provider_created_at TEXT,
                    received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,raw_event TEXT NOT NULL)""")
                cur = db.execute("""INSERT OR IGNORE INTO payment_ledger
                    (event_id,event_type,subscription_id,product_code,gross_amount,currency,
                     platform_fee_amount,processing_fee_estimate,net_estimate,entry_status,
                     provider_created_at,raw_event)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (event_key,event_type,subscription_id,"netcmd_pro",float(gross),currency,
                     float(platform_fee),float(processing_fee),
                     float(gross-platform_fee-processing_fee-payout_fee_estimate),
                     "recognized_estimate",_iso_timestamp(event.get("created")),json.dumps(event)))
                first_financial_record = cur.rowcount == 1
    except Exception as exc:
        print(f"payment_ledger: write failed; error_type={type(exc).__name__}", flush=True)
        raise HTTPException(status_code=503, detail="Payment ledger temporarily unavailable.")
    store.record_payment_event(event_key, event_type, subscription_id)
    # Never send a second sale notification for a provider retry.
    if first_financial_record:
        await asyncio.to_thread(notify_sale, event_type, membership)

    return {"ok": True, "membership_status": "active", "task_id": task_id,
            "assigned_agents": len(load_agents())}



class ProviderPayoutInput(BaseModel):
    provider_payout_id: str = Field(min_length=2, max_length=180)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    status: str = Field(default="paid", pattern="^(pending|paid|failed|reversed)$")
    paid_at: datetime | None = None
    note: str = Field(default="", max_length=500)


class BankSettlementInput(BaseModel):
    provider_payout_id: str = Field(min_length=2, max_length=180)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    bank_reference: str = Field(default="", max_length=180)
    received_at: datetime
    note: str = Field(default="", max_length=500)


@app.get("/api/payments/status", dependencies=[Depends(require_api_key)])
def payments_status():
    webhook_secret = bool(os.getenv("BMC_WEBHOOK_SECRET", "").strip())
    membership_level = bool(os.getenv("BMC_PRO_MEMBERSHIP_LEVEL_ID", "").strip())
    checkout = os.getenv("BMC_PRO_CHECKOUT_URL", "https://buymeacoffee.com/sevketkaynar").strip()
    return {
        "provider":"Buy Me a Coffee",
        "price_usd":os.getenv("BMC_PRO_PRICE_USD","69"),
        "checkout_configured":checkout.startswith("https://buymeacoffee.com/"),
        "webhook_secret_configured":webhook_secret,
        "membership_level_configured":membership_level,
        "ready_for_live_membership":bool(webhook_secret and membership_level and checkout.startswith("https://buymeacoffee.com/")),
        "webhook_endpoint":"https://ai-company-ferd.onrender.com/webhooks/buymeacoffee",
        "mode":"live_events_only; test events ignored"
    }


@app.get("/api/payments/summary", dependencies=[Depends(require_api_key)])
def payments_summary(months: int = 12):
    months = max(1, min(months, 24))
    try:
        ledger = store._request("payment_ledger", params={
            "select":"*", "order":"received_at.desc", "limit":"2000"
        })
        payouts = store._request("provider_payouts", params={
            "select":"*", "order":"created_at.desc", "limit":"500"
        })
        settlements = store._request("bank_settlements", params={
            "select":"*", "order":"received_at.desc", "limit":"500"
        })
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Payment report unavailable: {type(exc).__name__}")
    from collections import defaultdict
    monthly = defaultdict(lambda: {"gross": Decimal("0"), "platform_fees": Decimal("0"),
                                   "processing_fee_estimate": Decimal("0"), "net_estimate": Decimal("0"),
                                   "events": 0})
    currency_totals = defaultdict(lambda: {"gross": Decimal("0"), "platform_fees": Decimal("0"),
                                           "processing_fee_estimate": Decimal("0"), "net_estimate": Decimal("0")})
    for row in ledger:
        month = str(row.get("received_at",""))[:7]
        currency = str(row.get("currency","USD")).upper()
        if not month: continue
        key = f"{month}|{currency}"
        bucket = monthly[key]
        totals = currency_totals[currency]
        bucket["gross"] += Decimal(str(row.get("gross_amount",0)))
        bucket["platform_fees"] += Decimal(str(row.get("platform_fee_amount",0)))
        bucket["processing_fee_estimate"] += Decimal(str(row.get("processing_fee_estimate",0)))
        bucket["net_estimate"] += Decimal(str(row.get("net_estimate",0)))
        bucket["events"] += 1
        totals["gross"] += Decimal(str(row.get("gross_amount",0)))
        totals["platform_fees"] += Decimal(str(row.get("platform_fee_amount",0)))
        totals["processing_fee_estimate"] += Decimal(str(row.get("processing_fee_estimate",0)))
        totals["net_estimate"] += Decimal(str(row.get("net_estimate",0)))
    def by_currency(rows, key):
        totals = defaultdict(lambda: Decimal("0.00"))
        for row in rows:
            totals[str(row.get("currency","USD")).upper()] += Decimal(str(row.get(key,0)))
        return {cur:str(val.quantize(Decimal("0.01"))) for cur,val in totals.items()}
    paid_payouts = [p for p in payouts if str(p.get("status","")).lower() == "paid"]
    recent_months = set(sorted({k.split("|",1)[0] for k in monthly})[-months:])
    return {
        "currency_note":"All totals are separated by currency; currencies are never added together.",
        "ledger_entries":len(ledger),
        "totals_by_currency":{cur:{k:str(v.quantize(Decimal("0.01"))) for k,v in vals.items()}
                              for cur,vals in currency_totals.items()},
        "gross_recorded":by_currency(ledger,"gross_amount"),
        "platform_fees_recorded_or_estimated":by_currency(ledger,"platform_fee_amount"),
        "processing_fees_estimated":by_currency(ledger,"processing_fee_estimate"),
        "provider_payouts":payouts,
        "provider_payout_total_paid":by_currency(paid_payouts,"amount"),
        "bank_settlements":settlements,
        "bank_received_total":by_currency(settlements,"amount"),
        "monthly":[{"month":k.split("|",1)[0],"currency":k.split("|",1)[1],
                    **{n:(str(v) if isinstance(v,Decimal) else v) for n,v in val.items()}}
                   for k,val in sorted(monthly.items()) if k.split("|",1)[0] in recent_months],
        "reconciliation":"Provider payouts and bank settlements are separate manual/provider records; bank receipt is never inferred from a sale webhook."
    }


@app.post("/api/payments/payouts", dependencies=[Depends(require_api_key)])
def record_provider_payout(payload: ProviderPayoutInput):
    try:
        rows=store._request("provider_payouts","POST",{"on_conflict":"provider_payout_id"},{
            "provider":"buymeacoffee","provider_payout_id":payload.provider_payout_id,
            "amount":str(payload.amount),"currency":payload.currency.upper(),
            "status":payload.status,"paid_at":payload.paid_at.isoformat() if payload.paid_at else None,
            "note":payload.note
        },"resolution=merge-duplicates,return=representation")
        return {"ok":True,"payout":rows[0] if rows else None}
    except Exception as exc:
        raise HTTPException(status_code=503,detail=f"Payout record failed: {type(exc).__name__}")


@app.post("/api/payments/bank-settlements", dependencies=[Depends(require_api_key)])
def record_bank_settlement(payload: BankSettlementInput):
    try:
        rows=store._request("bank_settlements","POST",
            {"on_conflict":"provider_payout_id,bank_reference"},
            {"provider_payout_id":payload.provider_payout_id,
             "amount":str(payload.amount),"currency":payload.currency.upper(),
             "bank_reference":payload.bank_reference or None,
             "received_at":payload.received_at.isoformat(),"note":payload.note},
            "resolution=ignore-duplicates,return=representation")
        return {"ok":True,"duplicate":not bool(rows),"bank_settlement":rows[0] if rows else None}
    except Exception as exc:
        raise HTTPException(status_code=503,detail=f"Bank settlement record failed: {type(exc).__name__}")


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


# --- CRM: research-backed customer pipeline -----------------------------------------
from company.crm import (
    upsert_company as crm_upsert_company, list_companies as crm_list_companies,
    upsert_contact as crm_upsert_contact, create_offer as crm_create_offer,
    suppress_contact as crm_suppress_contact, list_followups as crm_list_followups,
    record_mail as crm_record_mail, list_contacts as crm_list_contacts,
    update_company_stage as crm_update_company_stage,
)

class CRMCompanyInput(BaseModel):
    company_name: str = Field(min_length=2, max_length=180)
    country: str = Field(default="Unknown", max_length=80)
    website: str | None = Field(default=None, max_length=500)
    industry: str | None = Field(default=None, max_length=120)
    company_size: str | None = Field(default=None, max_length=80)
    source_name: str = Field(min_length=2, max_length=120)
    source_url: str = Field(min_length=8, max_length=1000)
    source_type: str = Field(default="public_web", max_length=60)
    public_contact_channel: str | None = Field(default=None, max_length=300)
    business_email: str | None = Field(default=None, max_length=254)
    need_summary: str | None = Field(default=None, max_length=1500)
    fit_reason: str | None = Field(default=None, max_length=1500)

class CRMContactInput(BaseModel):
    full_name: str | None = Field(default=None, max_length=160)
    role: str | None = Field(default=None, max_length=120)
    email: str = Field(min_length=5, max_length=254)
    source_name: str = Field(min_length=2, max_length=120)
    source_url: str = Field(min_length=8, max_length=1000)
    legal_basis: str = Field(default="unverified", max_length=80)
    consent_status: str = Field(default="unknown", pattern="^(unknown|consented|withdrawn|not_required_verified)$")

class CRMStageInput(BaseModel):
    stage: str = Field(pattern="^(new|qualified|proposal|negotiation|won|lost|nurture|suppressed)$")

class CRMSuppressInput(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    reason: str = Field(min_length=3, max_length=300)

class CRMFollowupInput(BaseModel):
    company_id: str
    contact_id: str | None = None
    offer_id: str | None = None
    due_at: datetime
    note: str = Field(default="", max_length=500)

class CRMEmailInput(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    subject: str = Field(default="", max_length=200)
    body: str = Field(min_length=1, max_length=10000)
    external_message_id: str = ""
    thread_id: str = ""

@app.get("/crm")
def crm_dashboard():
    return FileResponse(WEB_DIR / "crm.html")

@app.get("/api/crm/status", dependencies=[Depends(require_api_key)])
def crm_status():
    return {
        "enabled": True,
        "database": "supabase" if database_status()["backend"] == "supabase" else "sqlite",
        "pipeline": ["TR+global research", "lead dedupe", "evidence capture", "fit scoring",
                     "needs analysis", "personalized proposal", "draft+followup",
                     "inbound classification", "approved-facts replies", "suppression list"],
        "outbound_sending": False, "human_approval_required": True,
        "privacy": "public business sources only; no private personal-data scraping",
        "mailbox": services_status()["mail"],
    }

@app.get("/api/crm/companies", dependencies=[Depends(require_api_key)])
def crm_companies(q: str = "", stage: str | None = None, limit: int = 100):
    try:
        return {"companies": crm_list_companies(store, limit, q, stage)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"CRM database unavailable: {type(exc).__name__}")

@app.post("/api/crm/companies", dependencies=[Depends(require_api_key)])
def crm_add_company(payload: CRMCompanyInput):
    try:
        return crm_upsert_company(payload.model_dump(), store)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)[:240])

@app.get("/api/crm/contacts", dependencies=[Depends(require_api_key)])
def crm_contacts(company_id: str | None = None):
    return {"contacts": crm_list_contacts(company_id, store)}

@app.post("/api/crm/companies/{company_id}/contacts", dependencies=[Depends(require_api_key)])
def crm_add_contact(company_id: str, payload: CRMContactInput):
    try:
        return crm_upsert_contact(company_id, payload.model_dump(), store)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

@app.patch("/api/crm/companies/{company_id}/stage", dependencies=[Depends(require_api_key)])
def crm_set_stage(company_id: str, payload: CRMStageInput):
    try:
        return crm_update_company_stage(company_id, payload.stage, store)
    except KeyError:
        raise HTTPException(status_code=404, detail="Company not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

@app.post("/api/crm/companies/{company_id}/offer", dependencies=[Depends(require_api_key)])
def crm_offer(company_id: str, product_name: str = "NetCmd PRO"):
    try:
        return crm_create_offer(company_id, product_name, store)
    except KeyError:
        raise HTTPException(status_code=404, detail="Company not found")
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

@app.get("/api/crm/offers", dependencies=[Depends(require_api_key)])
def crm_offers(limit: int = 100):
    return {"offers": store._request("crm_offers", params={
        "select":"*", "order":"created_at.desc", "limit":str(max(1,min(limit,250)))
    })}

@app.post("/api/crm/suppress", dependencies=[Depends(require_api_key)])
def crm_suppress(payload: CRMSuppressInput):
    try:
        return crm_suppress_contact(payload.email, payload.reason, "owner_manual", store)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

@app.get("/api/crm/followups", dependencies=[Depends(require_api_key)])
def crm_followups():
    return {"followups": crm_list_followups(store)}

@app.post("/api/crm/followups", dependencies=[Depends(require_api_key)])
def crm_add_followup(payload: CRMFollowupInput):
    row = {"followup_id":"fu-"+uuid.uuid4().hex[:12], **payload.model_dump(),
           "due_at":payload.due_at.astimezone(timezone.utc).isoformat(),
           "status":"pending", "created_at":datetime.now(timezone.utc).isoformat()}
    store._request("crm_followups","POST",body=row,prefer="return=minimal")
    return row

@app.get("/api/crm/mail", dependencies=[Depends(require_api_key)])
def crm_mail(limit: int = 100):
    return {"messages":store._request("crm_mail_log",params={
        "select":"*", "order":"created_at.desc", "limit":str(max(1,min(limit,250)))
    })}

@app.post("/api/crm/mail/classify", dependencies=[Depends(require_api_key)])
def crm_classify_mail(payload: CRMEmailInput):
    return crm_record_mail(payload.email, "inbound", payload.subject, payload.body,
                           payload.external_message_id, payload.thread_id, store)

@app.post("/api/crm/research", dependencies=[Depends(require_api_key)])
def crm_research(country: str = "both"):
    if country not in {"both","TR","global"}:
        raise HTTPException(status_code=422, detail="country must be both, TR or global")
    description = (
        "Research qualified B2B companies for NetCmd PRO. Target region: "
        + ("Turkey and global" if country == "both" else "Turkey" if country == "TR" else "outside Turkey")
        + ". Use public company sources only. Return up to 10 companies in a clearly delimited "
        "CRM_LEADS_JSON: [ ... ] block. Each item: company_name,country,website,industry,"
        "source_name,source_url,public_contact_channel,need_summary,fit_reason. "
        "No personal emails, no private individuals, no invented facts, no outreach. "
        "Only cite URLs actually used; if evidence is insufficient, return an empty array."
    )
    task = store.create_task(description, task_id="crm-research-" + uuid.uuid4().hex[:10])
    agents = [a.id for a in load_agents() if a.id in {
        "ceo","research_intelligence","marketing_growth","product_business","network_infrastructure"
    }]
    store.assign_agents(task["task_id"], agents)
    return {"task_id":task["task_id"],"status":"queued","assigned_agents":agents}
