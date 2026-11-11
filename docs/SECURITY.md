# Security baseline

- Never commit real tokens, passwords, API keys, private keys, or personal data.
- Telegram task intake requires an explicit numeric chat ID allowlist.
- Use a dedicated Telegram bot for this company; do not reuse another project's bot token by default.
- Unauthorized Telegram chats are ignored.
- The Telegram adapter only creates SQLite task records. It does not execute commands or invoke agents.
- Keep the repository private if project details, internal topology, or operational metadata are added.
- Shell execution and autonomous external writes remain disabled.
- Publishing, deployments, spending, deletion, Git pushes, pull requests, and network-device changes require a separate human approval step.
- Approval records are not execution authorization for an unspecified action.
- Do not print Telegram tokens or message contents in logs.
- Rotate a token immediately if it is exposed; update the local environment only.
