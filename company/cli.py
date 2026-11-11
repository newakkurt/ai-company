import argparse
from .orchestrator import create_task, doctor

def main():
    parser = argparse.ArgumentParser(prog="ai-company")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Check local scaffold")
    task = sub.add_parser("task", help="Create a local task plan")
    task.add_argument("description")
    args = parser.parse_args()

    if args.command == "doctor":
        for line in doctor():
            print(line)
    elif args.command == "task":
        record = create_task(args.description)
        print(f"Task created: {record['task_id']}")
        print(f"Status: {record['status']}")
        print(f"File: data/tasks/{record['task_id']}.json")
        print("No agent, external API, shell command, or production action was executed.")

if __name__ == "__main__":
    main()
