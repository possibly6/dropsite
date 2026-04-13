#!/usr/bin/env python3
"""🔻 DropSite CLI — manage your agent workspace from the terminal."""

import sys
import json
import argparse
from pathlib import Path
from .dropsite import DropSite, TaskBuilder


def main():
    parser = argparse.ArgumentParser(prog="dropsite", description="🔻 DropSite CLI")
    sub = parser.add_subparsers(dest="command")

    # init
    p_init = sub.add_parser("init", help="Initialize a workspace")
    p_init.add_argument("path", help="Workspace directory")

    # register
    p_reg = sub.add_parser("register", help="Register an agent")
    p_reg.add_argument("path", help="Workspace directory")
    p_reg.add_argument("--name", required=True)
    p_reg.add_argument("--role", default="worker")

    # drop
    p_drop = sub.add_parser("drop", help="Drop a task")
    p_drop.add_argument("path", help="Workspace directory")
    p_drop.add_argument("--from", dest="from_agent", required=True)
    p_drop.add_argument("--to", dest="to_agent", default=None)
    p_drop.add_argument("--title", required=True)
    p_drop.add_argument("--type", dest="task_type", default="general")
    p_drop.add_argument("--payload", default="{}")
    p_drop.add_argument("--priority", type=int, default=5)

    # inbox
    p_inbox = sub.add_parser("inbox", help="List inbox tasks")
    p_inbox.add_argument("path", help="Workspace directory")
    p_inbox.add_argument("--agent", default=None)

    # list
    p_list = sub.add_parser("list", help="List tasks in a folder")
    p_list.add_argument("path", help="Workspace directory")
    p_list.add_argument("folder", choices=["inbox", "active", "done", "failed", "blocked", "feedback"])

    # stats
    p_stats = sub.add_parser("stats", help="Workspace stats")
    p_stats.add_argument("path", help="Workspace directory")

    # feedback
    p_fb = sub.add_parser("feedback", help="Respond to feedback request")
    p_fb.add_argument("path", help="Workspace directory")
    p_fb.add_argument("task_id")
    p_fb.add_argument("response")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "init":
        ds = DropSite(args.path)
        print(f"🔻 Workspace initialized at {args.path}")

    elif args.command == "register":
        ds = DropSite(args.path)
        ds.register_agent(args.name, args.role)
        print(f"🔻 Agent '{args.name}' registered ({args.role})")

    elif args.command == "drop":
        ds = DropSite(args.path)
        payload = json.loads(args.payload)
        task = (
            TaskBuilder(args.title, args.from_agent)
            .assign(args.to_agent)
            .priority(args.priority)
            .context(payload)
            .tag(args.task_type)
            .build()
        )
        tid = ds.submit(task)
        print(f"🔻 Task dropped: {tid}")

    elif args.command == "inbox":
        ds = DropSite(args.path)
        tasks = ds.list_tasks("inbox", agent=args.agent)
        if not tasks:
            print("  (empty)")
        for t in tasks:
            print(f"  [{t.id}] P{t.priority} {t.title} (from: {t.created_by})")

    elif args.command == "list":
        ds = DropSite(args.path)
        tasks = ds.list_tasks(args.folder)
        if not tasks:
            print(f"  ({args.folder}/ is empty)")
        for t in tasks:
            print(f"  [{t.id}] {t.title} — {t.status}")

    elif args.command == "stats":
        ds = DropSite(args.path)
        s = ds.stats()
        print("🔻 Workspace Stats:")
        for folder, count in s.items():
            bar = "█" * count
            print(f"  {folder:10} {count:3d} {bar}")

    elif args.command == "feedback":
        ds = DropSite(args.path)
        ds.respond_feedback(args.task_id, args.response)
        print(f"🔻 Feedback submitted for {args.task_id}")


if __name__ == "__main__":
    main()
