# Multi-assistant collaboration rules

More than one AI assistant (Claude, others) and the owner change this repository.
`main` auto-deploys to Render: a bad commit becomes a failed deploy, and every deploy
restarts the free-tier instance and interrupts the live worker mid-task.

1. **Never push directly to `main`.** Work on a branch named `ai/<tool>/<topic>` and open a pull request.
2. **Tests first.** `python -m unittest discover -s tests` must pass locally before you push
   (CI runs Python 3.10, 3.11 and 3.12). For a quick syntax check: `python -m compileall -q company app.py`.
3. **Sync before you start.** `git fetch origin`, read `git log origin/main -10`, and check open
   branches and pull requests for the files you plan to touch. Do not start a second change in the same area.
4. **Small, focused changes.** No reformatting, line-ending rewrites or drive-by refactors of files you are not fixing.
5. **Merge = deploy.** Merge one pull request at a time, only when tests are green, and wait until
   the Render deploy is `live` before merging the next one.
6. **Approval gates belong to the owner.** Do not weaken `company/harness/escalation.py` (HIGH_RISK, `classify_risk`),
   `company/policies/` or any approval or privacy rule unless the pull request description states the
   owner's explicit approval and a test proves real risky requests still escalate.
7. **No secrets** in commits, logs, pull requests or chat. Reference variable names only.
8. **No external actions** (send, publish, spend, delete data, change network devices) without the owner's
   explicit approval for that exact action. See `CLAUDE.md` and `ANAYASA.md`.
9. **Record what you changed** in the pull request: files, test result, risks, and any approval you need.
