# Agent Operating Guide

Before acting:
1. Read ANAYASA.md (incl. "Agent Harness Kuralları"; code in company/harness/) and the relevant project entry.
2. Turn the request into a bounded objective with acceptance criteria.
3. Prefer inspection and plans before modifications.
4. Keep changes isolated to the requested repository.
5. Never expose secrets in output.

For every task:
- Create a task record.
- Identify owner agent and required inputs.
- Separate facts, assumptions, and recommendations.
- Run relevant tests.
- Return changed files, test results, risks, and required approval.

Do not publish, deploy, spend money, delete data, or modify real network devices without explicit approval for that exact action.

Multi-assistant rules: more than one AI assistant works in this repository and `main` auto-deploys. Read `AGENTS.md` (branch + PR, tests first, merge one at a time) before changing anything.
