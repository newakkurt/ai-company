"""Cloud API and minimal dashboard for the 13-role AI Company."""
from __future__ import annotations

import hmac
import os
import threading
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from company.agents import agent_summary, load_agents
from company.store import TaskStore
from company.agent_runner import run_task

ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
DB_PATH = Path(os.getenv("AI_COMPANY_DB_PATH", "/tmp/ai-company/company.db"))
store = TaskStore(DB_PATH)
app = FastAPI(title="New Akkurt AI Company", version="0.2.0")
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
    return {
        "gemini": bool(os.getenv("GEMINI_API_KEY")),
        "ollama": bool(os.getenv("AI_COMPANY_OLLAMA_URL")),
        "model": os.getenv("AI_COMPANY_GEMINI_MODEL", "gemini-2.5-flash"),
        "ready": bool(os.getenv("GEMINI_API_KEY") or os.getenv("AI_COMPANY_OLLAMA_URL")),
    }


@app.get("/healthz")
def healthz():
    return {"ok": True, "service": "ai-company", "agents": len(load_agents())}


@app.get("/")
def dashboard():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/api/status", dependencies=[Depends(require_api_key)])
def status():
    return {
        "service": "New Akkurt AI Company",
        "agents": len(load_agents()),
        "provider": provider_status(),
        "mode": "analysis_only",
        "external_actions_enabled": False,
        "database": "sqlite_ephemeral_unless_external_volume_configured",
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
    # Assign every registered role. Assignment is not execution.
    store.assign_agents(item["task_id"], [agent.id for agent in load_agents()])
    return {"task_id": item["task_id"], "status": "planned", "assigned_agents": 13}


def _execute_analysis(task_id: str) -> None:
    state = _run_state.setdefault(task_id, {})
    state.update(status="queued", message="Waiting for the analysis worker.")
    _run_lock.acquire()
    try:
        state.update(status="running", message="13 role agents are preparing analysis.")
        results = run_task(task_id, store=store)
        state.update(status="completed", result_count=len(results), message="Analysis saved.")
    except Exception as exc:  # noqa: BLE001 - report sanitized failure to the dashboard
        state.update(status="failed", message=f"Analysis failed: {type(exc).__name__}")
    finally:
        _run_lock.release()


@app.post("/api/tasks/{task_id}/run", dependencies=[Depends(require_api_key)])
def start_analysis(task_id: str, background: BackgroundTasks):
    item = store.get_task(task_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if not provider_status()["ready"]:
        raise HTTPException(
            status_code=503,
            detail="No cloud or local model is configured. Add GEMINI_API_KEY in Render environment variables.",
        )
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


@app.get("/api/health", dependencies=[Depends(require_api_key)])
def private_health():
    return {"ok": True, "provider": provider_status(), "agent_count": len(load_agents())}
