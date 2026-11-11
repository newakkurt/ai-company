# Continuous AI Agent Worker

## Execution model

The AI Company web process is not a durable worker. Its FastAPI `BackgroundTasks` are process-local and can be interrupted by a restart or a free-instance spin-down.

This implementation adds a Supabase-backed task consumer:
- Claims only tasks in `planned` state with `execution_mode=dry_run`.
- Uses a conditional database update so only one poller can claim a task.
- Persists each specialist's output as it is generated.
- Marks the task and assignments `completed` or `failed`.
- Does not send messages, publish content, deploy, spend money, or modify customer devices.
- Logs task IDs, counts, and exception classes only; it never prints API keys or model output.

## Zero-cost polling mode

`.github/workflows/agent-worker.yml` starts a one-task worker run every five minutes using GitHub-hosted runners. This avoids creating a paid Render Background Worker and leaves the existing Render web service unchanged.

This is recurring polling, **not a guaranteed 24/7 process**. GitHub scheduled workflows can be delayed, and a task only starts when a scheduled/manual workflow run is available. A true always-on Render Background Worker requires a paid Render compute plan; the current Render Free plan does not support worker services.

## One-time repository setup

In GitHub, open:

`newakkurt/ai-company → Settings → Secrets and variables → Actions → New repository secret`

Create these four secrets by copying the matching values from the existing Render `ai-company` service Environment page. Do not paste secret values into chat, issues, commits, or logs.

| Secret name | Source |
|---|---|
| `SUPABASE_URL` | Render service environment |
| `SUPABASE_ANON_KEY` | Render service environment |
| `SUPABASE_DB_GATE_KEY` | Render service environment |
| `GEMINI_API_KEY` | Render service environment |

After all four secrets exist, the next five-minute schedule run can consume one pending dry-run task. You can also start it manually from GitHub Actions → Continuous AI Agent Worker → Run workflow.

If a secret is missing, the workflow safely reports that it is paused and does not fall back to local SQLite.

## Run locally or on a dedicated worker

With the same four environment variables set securely:

```bash
python -m company.worker --once
python -m company.worker --poll-seconds 15
```

The second command is the long-running queue consumer intended for a dedicated Background Worker if a paid plan is approved later.

## Recovery and monitoring

- `planned`: waiting for a worker.
- `running`: claimed by a worker.
- `completed`: all assigned agent outputs were persisted.
- `failed`: an execution error occurred; inspect the task's events and retry only after review.

A process crash after claiming a task can leave it in `running`. Do not automatically reset such tasks without checking whether outputs were already persisted; this avoids duplicate Gemini calls and duplicated outputs. A future lease/heartbeat migration can add automatic stale-task recovery once the basic worker is deployed and observed.

## Validation

Run:

```bash
python -m unittest tests.test_continuous_worker -v
python -m unittest discover -s tests -v
```
