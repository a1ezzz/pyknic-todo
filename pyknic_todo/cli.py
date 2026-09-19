"""CLI interface for pyknic-todo."""

# TODO: refactor this

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Optional, Sequence

from .storage.proto import (
    ToDoStorageProto,
)

from .storage.storage import (
    storage_factory,
)

from .models import (
    EndCondtionType,
    RecurrenceScheduleType,
    Task,
    TaskPriority,
    TaskStatus,
    RecurrenceRule,
    EndCondition
)

from pyknic.lib.uri import URI

# TODO: replace cli with settings!
# data_dir: Path = Field(
#     default=Path("./data"),
#     validation_alias=AliasChoices(
#         "PYKNIC_TODO_DATA_DIR", "TODO_DATA_DIR", "data_dir"
#     ),
#     description="Directory to store JSON data",
# )


def create_parser() -> argparse.ArgumentParser:

    parser = argparse.ArgumentParser(
        prog="pyknic-todo",
        description="pyknic-todo: Simple CLI utility for todo task management",
    )

    parser.add_argument(
        "--storage-uri",
        dest="storage_uri",
        required=True  # TODO: set something to default!
        # TODO: update help!
        # help=f"Directory to store JSON data (defaults to {settings.data_dir} or $PYKNIC_TODO_DATA_DIR)",
    )

    # parser.add_argument(
    #     "--data-dir",
    #     dest="data_dir",
    #     default=None,
    #     help=f"Directory to store JSON data (defaults to {settings.data_dir} or $PYKNIC_TODO_DATA_DIR)",
    # )
    # parser.add_argument(
    #     "--storage-type",
    #     dest="storage_type",
    #     default=None,
    #     help=f"Storage backend type (defaults to {settings.storage_type} or $PYKNIC_TODO_STORAGE_TYPE)",
    # )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # add command
    add_parser = subparsers.add_parser("add", help="Create a new task")
    add_parser.add_argument("title", help="Task title")
    add_parser.add_argument("-d", "--description", default="", help="Task description")
    add_parser.add_argument(
        "-p",
        "--priority",
        default=TaskPriority.medium,
        choices=sorted([
            x.value for x in TaskPriority
        ]),
    )
    add_parser.add_argument(
        "-s",
        "--status",
        choices=sorted([x.value for x in TaskStatus]),
    )
    add_parser.add_argument("--due", "--due-date", dest="due_date", default=None, help="Due date (ISO format)")
    add_parser.add_argument(
        "-t",
        "--tag",
        dest="tags",
        action="append",
        help="Tag for task (can be specified multiple times or comma-separated)",
    )
    add_parser.add_argument("--project", dest="project", default=None, help="Project name")

    # status command
    status_parser = subparsers.add_parser("status", help="Change status of a task")
    status_parser.add_argument("task_id", help="Task ID or ID prefix")
    status_parser.add_argument(
        "new_status",
        choices=sorted([x.value for x in TaskStatus]),
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
        choices=sorted([x.value for x in RecurrenceScheduleType]),
        help="Schedule type: 'rrule' or 'cron' (default: rrule)",
    )
    repeat_parser.add_argument(
        "--end-type",
        default="never",
        choices=sorted([x.value for x in EndCondtionType]),
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
        choices=sorted([x.value for x in TaskStatus]),
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


def handle_add(storage: ToDoStorageProto, args: argparse.Namespace) -> int:
    tags: list[str] = []
    if args.tags:
        for t in args.tags:
            for part in t.split(","):
                clean = part.strip()
                if clean and clean not in tags:
                    tags.append(clean)

    task = Task(
        title=args.title,
        description=args.description,
        priority=TaskPriority(args.priority) if args.priority else TaskPriority.medium, 
        due_date=args.due_date,
        tags=tags,
        project=args.project,
    )

    storage.append_task(task)
    task_status = storage.task_status(task.id)
    print(f"Task created: [{task_status}] {task.title} (ID: {task.id})")
    return 0


def handle_status(storage: ToDoStorageProto, args: argparse.Namespace) -> int:
    storage.set_task_status(
        task_id_query=args.task_id,
        new_status=getattr(TaskStatus, args.new_status),  # TODO: handle invalid status
        comment=args.comment,
    )
    print(f"Task {args.task_id} status updated to '{args.new_status}'")
    return 0


def handle_done(storage: ToDoStorageProto, args: argparse.Namespace) -> int:
    task = storage.set_task_status(
        task_id_query=args.task_id,
        new_status=TaskStatus.done,
        comment=args.comment,
    )
    print(f"Task {task.id} marked as done")
    return 0


def handle_repeat(storage: ToDoStorageProto, args: argparse.Namespace) -> int:

    rule = RecurrenceRule(
        schedule_type=args.schedule_type,
        schedule_expression=args.expression,
        end_condition=EndCondition(
            condition_type=args.end_type,
            until_date=args.until_date,
            max_occurrences=args.max_occurrences,
        )
    )

    task = storage.set_task_recurrence(
        task_id_query=args.task_id,
        rule=rule
    )
    print(
        f"Recurrence set for task {task.id}: "
        f"{rule.schedule_type} '{rule.schedule_expression}' (Rule ID: {rule.id})"
    )
    return 0


def is_completed_task(task: dict[str, Any]) -> bool:
    return task.get("status") == "done" or bool(task.get("completed_at"))


def is_deleted_task(task: dict[str, Any]) -> bool:
    return task.get("status") == "deleted" or bool(task.get("deleted_at"))


def handle_list(storage: ToDoStorageProto, args: argparse.Namespace) -> int:
    tasks = [x.model_dump(mode='json') for x in storage.load_tasks()]

    show_all = getattr(args, "all", False) or getattr(args, "mode", None) == "all"
    show_completed_only = getattr(args, "completed", False) or getattr(args, "mode", None) == "completed"
    include_completed = getattr(args, "include_completed", False)

    if args.status:
        tasks = [t for t in tasks if storage.task_status(t['id']).value == args.status]
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
        status = storage.task_status(t['id']) or ""
        priority = t.get("priority", "")
        recur = t.get("recurrence_rule_id") or "-"
        if len(recur) > 12:
            recur = recur[:12]
        title = t.get("title", "")
        print(f"{tid:<36} | {status:<11} | {priority:<8} | {recur:<12} | {title}")
    return 0


def main(
    argv: Optional[Sequence[str]] = None,
) -> int:

    parser = create_parser()
    args = parser.parse_args(argv)

    storage = storage_factory(URI.parse(args.storage_uri))

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
        else:
            parser.print_help()
            return 1
    except (KeyError, ValueError) as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
