"""CLI interface for pyknic-todo."""

# TODO: refactor this

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional, Sequence

from .settings import Settings
from .storage.proto import (
    AbstractStorage,
)

from .storage.storage import (
    StorageFactory,
    VALID_PRIORITIES,
    VALID_STATUSES,
)

from .models import (
    VALID_END_CONDITIONS,
    VALID_SCHEDULE_TYPES,
)


def create_parser(settings: Optional[Settings] = None) -> argparse.ArgumentParser:
    if settings is None:
        settings = Settings()

    parser = argparse.ArgumentParser(
        prog="pyknic-todo",
        description="pyknic-todo: Simple CLI utility for todo task management",
    )
    parser.add_argument(
        "--data-dir",
        dest="data_dir",
        default=None,
        help=f"Directory to store JSON data (defaults to {settings.data_dir} or $PYKNIC_TODO_DATA_DIR)",
    )
    parser.add_argument(
        "--storage-type",
        dest="storage_type",
        default=None,
        help=f"Storage backend type (defaults to {settings.storage_type} or $PYKNIC_TODO_STORAGE_TYPE)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # add command
    add_parser = subparsers.add_parser("add", help="Create a new task")
    add_parser.add_argument("title", help="Task title")
    add_parser.add_argument("-d", "--description", default="", help="Task description")
    add_parser.add_argument(
        "-p",
        "--priority",
        default=settings.default_priority,
        choices=sorted(VALID_PRIORITIES),
        help=f"Task priority (default: {settings.default_priority})",
    )
    add_parser.add_argument(
        "-s",
        "--status",
        default=settings.default_status,
        choices=sorted(VALID_STATUSES),
        help=f"Initial task status (default: {settings.default_status})",
    )
    add_parser.add_argument("--due", "--due-date", dest="due_date", default=None, help="Due date (ISO format)")
    add_parser.add_argument(
        "-t",
        "--tag",
        dest="tags",
        action="append",
        help="Tag for task (can be specified multiple times or comma-separated)",
    )
    add_parser.add_argument("--project", dest="project_id", default=None, help="Project ID")

    # status command
    status_parser = subparsers.add_parser("status", help="Change status of a task")
    status_parser.add_argument("task_id", help="Task ID or ID prefix")
    status_parser.add_argument(
        "new_status",
        choices=sorted(VALID_STATUSES),
        help="New status for the task",
    )
    status_parser.add_argument("-m", "--comment", default=None, help="Optional comment for state transition")

    # done command (shorthand)
    done_parser = subparsers.add_parser("done", help="Mark a task as done")
    done_parser.add_argument("task_id", help="Task ID or ID prefix")
    done_parser.add_argument("-m", "--comment", default="Completed via CLI", help="Optional comment")

    # repeat / recurrence command
    repeat_parser = subparsers.add_parser("repeat", help="Set recurrence schedule for a task")
    repeat_parser.add_argument("task_id", help="Task ID or ID prefix")
    repeat_parser.add_argument(
        "-e",
        "--expression",
        required=True,
        help="Recurrence expression (RRULE string like 'FREQ=WEEKLY' or Cron expression)",
    )
    repeat_parser.add_argument(
        "-t",
        "--type",
        dest="schedule_type",
        default="rrule",
        choices=sorted(VALID_SCHEDULE_TYPES),
        help="Schedule type: 'rrule' or 'cron' (default: rrule)",
    )
    repeat_parser.add_argument(
        "--end-type",
        default="never",
        choices=sorted(VALID_END_CONDITIONS),
        help="Recurrence end condition type (default: never)",
    )
    repeat_parser.add_argument("--until", dest="until_date", default=None, help="Until date (ISO format)")
    repeat_parser.add_argument(
        "--count",
        dest="max_occurrences",
        type=int,
        default=None,
        help="Maximum occurrences count",
    )

    # list command
    list_parser = subparsers.add_parser("list", help="List tasks")
    list_parser.add_argument(
        "-a",
        "--all",
        "--show-all",
        "--all-tasks",
        action="store_true",
        dest="all",
        help="Show all tasks including completed and deleted",
    )
    list_parser.add_argument(
        "-c",
        "--completed",
        "--done",
        action="store_true",
        dest="completed",
        help="Show only completed tasks",
    )
    list_parser.add_argument(
        "--include-completed",
        action="store_true",
        dest="include_completed",
        help="Include completed tasks in the list",
    )
    list_parser.add_argument(
        "--mode",
        choices=["active", "all", "completed"],
        default=None,
        help="Display mode: 'active' (default), 'all', or 'completed'",
    )
    list_parser.add_argument(
        "-s",
        "--status",
        choices=sorted(VALID_STATUSES),
        default=None,
        help="Filter tasks by status",
    )
    list_parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON",
    )

    # config command
    config_parser = subparsers.add_parser("config", help="Show current configuration settings")
    config_parser.add_argument(
        "--json",
        action="store_true",
        help="Output settings as JSON",
    )

    return parser


def handle_add(storage: AbstractStorage, args: argparse.Namespace) -> int:
    tags: list[str] = []
    if args.tags:
        for t in args.tags:
            for part in t.split(","):
                clean = part.strip()
                if clean and clean not in tags:
                    tags.append(clean)

    task = storage.append_task(
        title=args.title,
        description=args.description,
        priority=args.priority,
        status=args.status,
        due_date=args.due_date,
        tags=tags,
        project_id=args.project_id,
    )
    print(f"Task created: [{task['status']}] {task['title']} (ID: {task['id']})")
    return 0


def handle_status(storage: AbstractStorage, args: argparse.Namespace) -> int:
    task = storage.set_task_status(
        task_id_query=args.task_id,
        new_status=args.new_status,
        comment=args.comment,
    )
    print(f"Task {task['id']} status updated to '{task['status']}'")
    return 0


def handle_done(storage: AbstractStorage, args: argparse.Namespace) -> int:
    task = storage.set_task_status(
        task_id_query=args.task_id,
        new_status="done",
        comment=args.comment,
    )
    print(f"Task {task['id']} marked as done")
    return 0


def handle_repeat(storage: AbstractStorage, args: argparse.Namespace) -> int:
    task, rule = storage.set_task_recurrence(
        task_id_query=args.task_id,
        schedule_type=args.schedule_type,
        schedule_expression=args.expression,
        end_condition_type=args.end_type,
        until_date=args.until_date,
        max_occurrences=args.max_occurrences,
    )
    print(
        f"Recurrence set for task {task['id']}: "
        f"{rule['schedule_type']} '{rule['schedule_expression']}' (Rule ID: {rule['id']})"
    )
    return 0


def is_completed_task(task: dict[str, Any]) -> bool:
    return task.get("status") == "done" or bool(task.get("completed_at"))


def is_deleted_task(task: dict[str, Any]) -> bool:
    return task.get("status") == "deleted" or bool(task.get("deleted_at"))


def handle_list(storage: AbstractStorage, args: argparse.Namespace) -> int:
    tasks = [x.model_dump() for x in storage.load_tasks()]

    show_all = getattr(args, "all", False) or getattr(args, "mode", None) == "all"
    show_completed_only = getattr(args, "completed", False) or getattr(args, "mode", None) == "completed"
    include_completed = getattr(args, "include_completed", False)

    if args.status:
        tasks = [t for t in tasks if t.get("status") == args.status]
    elif show_all:
        pass
    elif show_completed_only:
        tasks = [t for t in tasks if is_completed_task(t)]
    elif include_completed:
        tasks = [t for t in tasks if not is_deleted_task(t)]
    else:
        tasks = [
            t for t in tasks
            if not is_completed_task(t) and not is_deleted_task(t)
        ]

    if args.json:
        print(json.dumps(tasks, ensure_ascii=False, indent=2))
        return 0

    if not tasks:
        print("No tasks found.")
        return 0

    # Table view
    print(f"{'ID':<36} | {'STATUS':<11} | {'PRIORITY':<8} | {'RECUR':<12} | {'TITLE'}")
    print("-" * 80)
    for t in tasks:
        tid = t.get("id", "")
        status = t.get("status", "")
        priority = t.get("priority", "")
        recur = t.get("recurrence_rule_id") or "-"
        if len(recur) > 12:
            recur = recur[:12]
        title = t.get("title", "")
        print(f"{tid:<36} | {status:<11} | {priority:<8} | {recur:<12} | {title}")
    return 0


def handle_config(settings: Settings, args: argparse.Namespace) -> int:
    if args.json:
        print(settings.model_dump_json(indent=2))
        return 0

    print(f"data_dir: {settings.data_dir}")
    print(f"storage_type: {settings.storage_type}")
    print(f"schema_version: {settings.schema_version}")
    print(f"client_id_prefix: {settings.client_id_prefix}")
    print(f"default_priority: {settings.default_priority}")
    print(f"default_status: {settings.default_status}")
    return 0


def main(
    argv: Optional[Sequence[str]] = None,
    settings: Optional[Settings] = None,
) -> int:
    if settings is None:
        settings = Settings()

    parser = create_parser(settings=settings)
    args = parser.parse_args(argv)

    if args.data_dir:
        settings = settings.model_copy(update={"data_dir": Path(args.data_dir)})
    if getattr(args, "storage_type", None):
        settings = settings.model_copy(update={"storage_type": args.storage_type})

    storage = StorageFactory.create_storage(settings=settings)

    try:
        if args.command == "add":
            return handle_add(storage, args)
        elif args.command == "status":
            return handle_status(storage, args)
        elif args.command == "done":
            return handle_done(storage, args)
        elif args.command == "repeat":
            return handle_repeat(storage, args)
        elif args.command == "list":
            return handle_list(storage, args)
        elif args.command == "config":
            return handle_config(settings, args)
        else:
            parser.print_help()
            return 1
    except (KeyError, ValueError) as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
