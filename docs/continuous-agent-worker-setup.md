# Continuous AI Agent Worker

## Production execution model

The AI Company worker runs as an embedded, long-lived Python thread inside the existing Render web service. It uses the existing Render environment variables and polls the Supabase task queue every 15 seconds.

The worker:
- Claims only tasks in `planned` state with `execution_mode=dry_run`.
- Uses a conditional database update so only one poller can claim a task.
- Persists each specialist's output and assignment checkpoint as it is generated.
- Reclaims an interrupted task after 60 minutes without a saved-output heartbeat, then resumes by skipping agents whose outputs already exist.
- Marks completed or failed tasks and records audit events.
- Does not send messages, publish content, deploy, spend money, or modify customer devices.

## Zero-additional-cost keep-alive

The existing Render service is on the Free plan. Render free web services spin down after 15 minutes without inbound traffic and can restart at any time. The hosted readiness workflow therefore pings `/readyz` every five minutes and verifies:
- `worker.enabled=true`
- `worker.running=true`
- Gemini and Supabase are ready
- all 14 agents are registered
- `external_actions_enabled=false`

This keeps the existing web process active under normal scheduling, without a separate paid Worker or duplicated API secrets in GitHub.

**Limitations:** this is the best-effort $0 arrangement, not a strict 24/7 SLA. GitHub scheduled workflows may be delayed; Render Free can restart services; and the workspace has a shared 750 free-instance-hour monthly allowance. A dedicated Render Background Worker with guaranteed continuous compute requires a paid plan. Do not claim uninterrupted operation unless the live worker health checks continue passing.

## Render configuration

Set this additional non-secret environment variable on the existing `ai-company` Render web service:

```text
AI_COMPANY_EMBEDDED_WORKER=true
```

The service already needs these existing environment variables:
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_DB_GATE_KEY`
- `GEMINI_API_KEY`

Do not copy secret values into GitHub, source code, or chat. The embedded worker reads them from the Render service environment.

## Monitoring

- Live health endpoint: `https://ai-company-ferd.onrender.com/readyz`
- GitHub scheduled health monitor: `.github/workflows/health-monitor.yml` (every five minutes)
- Worker log prefix: `agent_worker:`
- Queue status: Supabase `tasks.status`
- Per-agent checkpoint: Supabase `assignments.status` and `agent_outputs`

Expected task lifecycle:
- `planned`: waiting for the worker.
- `running`: claimed by a worker.
- `completed`: all assigned agent outputs were persisted.
- `failed`: a handled execution error occurred; inspect events before retrying.

## Run locally or on a dedicated worker

With the existing four environment variables set securely:

```bash
python -m company.worker --once
python -m company.worker --poll-seconds 15
```

The second command is the long-running queue consumer intended for a dedicated Background Worker if a paid plan is approved later.

## Validation

```bash
python -m unittest tests.test_continuous_worker -v
python -m unittest discover -s tests -v
```
