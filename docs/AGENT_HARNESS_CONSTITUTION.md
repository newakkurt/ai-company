# Agent Harness Constitution (v1.0)

This is the enforceable operating baseline for New Akkurt AI Company. Existing product, CRM, billing and worker features remain in analysis/draft mode unless a narrowly scoped owner approval authorizes the exact next action.

## 15 mandatory principles

1. **Tiered routing and privacy-first.** Public, non-sensitive tasks may use configured cloud providers. Restricted/confidential task descriptions must never be sent to Gemini/Groq. Local model routing is fail-closed until an Ollama/local adapter is implemented and verified. Secrets and personal data must not be placed in task descriptions.
2. **State machines and traceability.** Task states are explicit; every state transition and decision must be persisted as an event with actor, timestamp, reason and safe parameters.
3. **Verification and human checkpoints.** Validate every tool output before downstream use. Publication, outbound communication, payment/refund, deletion, permission changes, deployment and infrastructure writes require scoped, one-time human approval.
4. **Bounded retries and escalation.** A task gets at most 3 total attempts (initial + 2 retries). Exhausted, ambiguous or high-risk tasks move to a blocked/dead-letter or approval queue; never retry indefinitely.
5. **Context and resource budgets.** Load only task-relevant agent capabilities and guidance. Set CPU/RAM/time, daily task and monthly spend budgets. A configured budget without metering is not considered enforced.
6. **Agent identity and least privilege.** Every agent has a stable ID, role, allowed capabilities and explicit denied capabilities. Unknown capabilities are denied.
7. **Task queue discipline.** Every task has an ID, owner, priority, deadline, idempotency key, lease/heartbeat and terminal state. Restart recovery must not duplicate side effects.
8. **Secrets and data protection.** Secrets are environment/secret-store only, never logs or Git. Encrypt sensitive records at rest and in transit; apply retention and deletion rules.
9. **Runtime safety.** Shell, arbitrary code execution, network-device writes and unrestricted internet access are disabled by default. Use allowlisted tools and isolated sandboxes for untrusted artifacts.
10. **Observability and alerting.** Health, readiness, queue age, retry count, provider quota, dead letters, budget and service errors are measurable and alertable.
11. **Quality and release gates.** Unit, integration, security, dependency and artifact-integrity tests must pass before release. Use versioned releases and rollback plans.
12. **Financial controls.** Meter provider usage and per-product cost; reconcile provider payment events separately from bank settlement. Never infer revenue from a webhook alone.
13. **CRM and customer lifecycle.** Use public business sources, record evidence/legal basis, deduplicate leads, honor suppression and opt-out, and keep outbound contact approval-controlled.
14. **Backup and disaster recovery.** Back up database, configuration and artifacts; encrypt backups; test restore; document RPO/RTO. A backup that has not been restore-tested is unverified.
15. **Continuous improvement.** Track task success, QA defect rate, product adoption, customer outcomes and contribution margin. Changes to policy require tests and a versioned audit record.

## Enforcement status

The governance helper and worker implement conservative screening of task descriptions and assembled prompts, cloud-route denial for non-public work, a process-local provider circuit breaker, a kill switch, least-privilege agent capability/tool allowlists, a daily task-count cap, and a three-total-attempt retry ceiling. Blocked tasks are moved to a terminal `blocked` state with an audit event. Existing scoped approval records remain the gate for protected actions.

Not yet active: local model inference (no Ollama adapter), persistent provider-spend metering, persistent circuit-breaker state across restarts, per-agent execution sandbox, encrypted backup/restore rehearsal, and live alert delivery. Do not mark these as active until verified.

## Configuration

- `AI_COMPANY_KILL_SWITCH=true`: pause worker task processing.
- `OLLAMA_BASE_URL` and `AI_COMPANY_LOCAL_MODEL`: declare a local model endpoint/model; this alone does not activate local inference until an adapter exists.
- `AI_COMPANY_DAILY_TASK_LIMIT`: worker-enforced daily task processing cap (default 20; counts the latest 100 task records).
- `AI_COMPANY_MONTHLY_SPEND_LIMIT_USD`: intended monthly spend cap (default 0; currently reporting/configuration only, not enforced until provider usage metering is implemented).
- Existing `AI_COMPANY_API_KEY`, Supabase and provider secrets remain in Render's secret environment only.

## Safety contract

No production merge/deploy, customer outreach, payment movement, refund, deletion or infrastructure write is authorized by this document. Approval must be action-specific, resource-specific, time-bounded and consumed once.
