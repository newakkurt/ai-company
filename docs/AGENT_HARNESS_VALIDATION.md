# Agent Harness Validation Plan

CI must run the full existing unittest suite on Python 3.10, 3.11 and 3.12.

Required focused checks:
- Restricted/confidential task descriptions are blocked before any cloud provider call.
- The complete assembled prompt is screened again immediately before every model request.
- Unknown agent IDs, capabilities and tools are denied by default.
- Kill switch pauses seeding, reminders and task processing.
- Daily task processing cap is applied before queue claim.
- Provider circuit breaker opens after three consecutive task-level provider failures and permits one half-open trial after cooldown.
- Task retry policy allows at most three total attempts.
- Governance status endpoint exposes policy state without secrets.
- Existing product publication, payment and outbound communication approval gates remain intact.

Release gate: do not merge to main or deploy production until CI is green and the owner explicitly approves the pull request and deployment.