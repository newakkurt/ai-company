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

if __name__ == "__main__":
    main()
