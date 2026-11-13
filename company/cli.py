import argparse

from .store import TaskStore
from .orchestrator import doctor


def main():
    from .config import load_local_env
    load_local_env()
    parser = argparse.ArgumentParser(prog="ai-company")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Check local scaffold")
    sub.add_parser("agents", help="List the 14 registered role agents")
    task = sub.add_parser("task", help="Create a local task")
    task.add_argument("description")
    plan = sub.add_parser("plan", help="Create a task and suggest agent assignments")
    plan.add_argument("description")
    plan.add_argument("--all-agents", action="store_true", help="Assign all 14 roles instead of keyword-selected specialists")
    run = sub.add_parser("run", help="Run local-model analysis for a planned task (analysis only)")
    run.add_argument("task_id")
    remember = sub.add_parser("remember", help="Save a local company knowledge note")
    remember.add_argument("title")
    remember.add_argument("body")
    remember.add_argument("--tags", default="")
    recall = sub.add_parser("recall", help="Search local company knowledge")
    recall.add_argument("query", nargs="?", default="")
    sub.add_parser("list", help="List recent tasks")
    approve = sub.add_parser("approve", help="Record human approval; does not execute")
    approve.add_argument("task_id")
    approve.add_argument("--note", default="")
    review = sub.add_parser("review", help="Human review queue (SQLite) for escalated work")
    review_sub = review.add_subparsers(dest="review_command", required=True)
    review_sub.add_parser("list", help="List pending items")
    for name in ("approve", "reject"):
        item = review_sub.add_parser(name, help=f"{name.title()} one queued item (records the decision only)")
        item.add_argument("review_id")
        item.add_argument("--note", default="")
    route = sub.add_parser("route-check", help="Dry-run privacy routing: which tier may see this text?")
    route.add_argument("text")
    route.add_argument("--kind", default="planning", choices=[k.value for k in __import__(
        "company.harness.routing", fromlist=["TaskKind"]).TaskKind])
    trace = sub.add_parser("trace", help="Show or verify a task's state-transition trace")
    trace.add_argument("task_id")
    trace.add_argument("--verify", action="store_true")
    sub.add_parser("telegram-poll", help="Receive allowlisted Telegram tasks")
    sub.add_parser("telegram-id", help="Show chat IDs from pending bot updates")
    args = parser.parse_args()

    if args.command == "doctor":
        for line in doctor():
            print(line)
        print(f"SQLite database: {TaskStore().db_path}")
    elif args.command == "agents":
        from .agents import agent_summary
        for index, agent in enumerate(agent_summary(), 1):
            print(f"{index:02d}. {agent['name']} [{agent['id']}]")
            print(f"    {agent['purpose']}")
        print("Mode: role registry + local model analysis; no external actions.")
    elif args.command in ("task", "plan"):
        store = TaskStore()
        item = store.create_task(args.description)
        print(f"Task: {item['task_id']}")
        print(f"Status: {item['status']} | Mode: {item['execution_mode']}")
        if args.command == "plan":
            from .agents import load_agents, route_task
            agent_ids = [agent.id for agent in load_agents()] if args.all_agents else route_task(args.description)
            assignments = store.assign_agents(item["task_id"], agent_ids)
            print("Suggested agents:")
            for assignment in assignments:
                print(f"- {assignment['agent_id']} ({assignment['status']})")
        print("Saved locally. No agent analysis or external action was executed.")
    elif args.command == "run":
        from .agent_runner import run_task
        try:
            results = run_task(args.task_id)
        except (KeyError, RuntimeError) as exc:
            parser.error(str(exc))
        for result in results:
            print(f"\n=== {result['agent_id']} ===\n")
            print(result["output"])
        print("\nAnalysis saved locally. No external action was executed.")
    elif args.command == "remember":
        note_id = TaskStore().remember(args.title, args.body, [x.strip() for x in args.tags.split(",") if x.strip()])
        print(f"Knowledge saved: {note_id}")
    elif args.command == "recall":
        notes = TaskStore().search_knowledge(args.query)
        if not notes:
            print("No matching knowledge notes.")
        for note in notes:
            print(f"\n{note['note_id']} — {note['title']}")
            print(note["body"])
            if note["tags"]:
                print("Tags: " + ", ".join(note["tags"]))
    elif args.command == "list":
        items = TaskStore().list_tasks()
        if not items:
            print("No tasks yet.")
        for item in items:
            print(f"{item['task_id']} | {item['status']} | {item['description']}")
    elif args.command == "approve":
        try:
            item = TaskStore().record_approval(args.task_id, "human", args.note)
        except (KeyError, ValueError) as exc:
            parser.error(str(exc))
        print(f"Approval recorded: {item['task_id']}")
        print("This records approval only; it does not run code, publish, deploy, spend, or change devices.")
    elif args.command == "review":
        from .harness.escalation import HumanReviewQueue
        queue = HumanReviewQueue()
        if args.review_command == "list":
            items = queue.list()
            if not items:
                print("No pending reviews.")
            for item in items:
                print(f"{item['review_id']} | {item['task_id']} | {item['reason']} | attempts={item['attempts']}")
        else:
            decision = "approved" if args.review_command == "approve" else "rejected"
            try:
                queue.decide(args.review_id, decision, "human", args.note)
            except (KeyError, ValueError) as exc:
                parser.error(str(exc))
            print(f"Review {decision}: {args.review_id}")
            print("This records the decision only; it does not run code, publish, deploy, spend, or change devices.")
    elif args.command == "route-check":
        import os
        from .harness.routing import TaskKind, Tier, TieredProvider, build_local_providers
        from .llm import _get_cloud_provider
        local = build_local_providers()
        router = TieredProvider(local[Tier.SMALL_LOCAL], local[Tier.LARGE_LOCAL], _get_cloud_provider(),
                                os.getenv("AI_COMPANY_ALLOW_CLOUD", "true").lower() in {"1", "true", "yes", "on"})
        order, decision = router.plan(TaskKind(args.kind), args.text)
        print(f"Sensitive: {decision.sensitive} {decision.findings or ''}")
        print("Eligible tiers (in order): " + (", ".join(t.value for t in order) or "NONE -> human review"))
        for tier, reason in decision.skipped:
            print(f"  skipped {tier}: {reason}")
    elif args.command == "trace":
        from .harness.state_machine import read_trace, verify_trace
        for record in read_trace(args.task_id):
            print(f"{record['seq']:>3} {record['ts']} {record['from']} -> {record['to']} "
                  f"({record['trigger']}) {record['params'] or ''}")
        if args.verify:
            ok, reason = verify_trace(args.task_id)
            print("Trace integrity: " + ("OK" if ok else "FAILED — " + reason))
            raise SystemExit(0 if ok else 1)
    elif args.command == "telegram-id":
        from .telegram import TelegramIntake
        try:
            bot = TelegramIntake(allowed_chat_ids=["__discovery_only__"])
            ids = bot.pending_chat_ids()
        except (ValueError, RuntimeError) as exc:
            parser.error(str(exc))
        if ids:
            print("Pending Telegram chat IDs (add only your own):")
            for chat_id in ids:
                print(chat_id)
        else:
            print("No pending messages. Send /start to your bot, then run this command again.")
        print("Run this before telegram-poll; do not share your bot token.")
    elif args.command == "telegram-poll":
        from .telegram import TelegramIntake
        try:
            bot = TelegramIntake()
        except ValueError as exc:
            parser.error(str(exc))
        print("Telegram intake active. Only allowlisted chat IDs can create tasks. Press Ctrl+C to stop.")
        try:
            bot.poll_forever()
        except KeyboardInterrupt:
            print("\nTelegram intake stopped.")


if __name__ == "__main__":
    main()
