import argparse
from .store import TaskStore
from .orchestrator import doctor

def main():
    parser = argparse.ArgumentParser(prog="ai-company")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Check local scaffold")
    task = sub.add_parser("task", help="Create a local task")
    task.add_argument("description")
    sub.add_parser("list", help="List recent tasks")
    approve = sub.add_parser("approve", help="Record human approval; does not execute")
    approve.add_argument("task_id")
    approve.add_argument("--note", default="")
    sub.add_parser("telegram-poll", help="Receive allowlisted Telegram tasks")
    sub.add_parser("telegram-id", help="Show chat IDs from pending bot updates")
    args = parser.parse_args()

    if args.command == "doctor":
        for line in doctor():
            print(line)
        print(f"SQLite database: {TaskStore().db_path}")
    elif args.command == "task":
        item = TaskStore().create_task(args.description)
        print(f"Task: {item['task_id']}")
        print(f"Status: {item['status']} | Mode: {item['execution_mode']}")
        print("Saved locally. No agent or external action was executed.")
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
