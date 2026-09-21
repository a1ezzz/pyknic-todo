"""Unit tests for pyknic-todo CLI and storage."""

from pyknic.lib.uri import URI

from pyknic_todo.cli import main
from pyknic_todo.models import TaskPriority, RecurrenceScheduleType, TaskStatus

from pyknic_todo.storage.json import JsonStorage


class TestCLI:

    def test_cli_end_to_end(self, json_tmp_uri: URI) -> None:
        storage_arg = f"--storage-uri={str(json_tmp_uri)}"

        # 1. Add task via CLI
        code = main([storage_arg, "add", "-t", "Write docs", "-p", "high", "--tags", "docs,work"])
        assert(code == 0)

        tasks = JsonStorage(json_tmp_uri).load_tasks()
        assert(len(tasks) == 1)
        task_id = tasks[0].id
        assert(tasks[0].title == "Write docs")
        assert(tasks[0].priority == TaskPriority.high)
        assert(tasks[0].tags == ["docs", "work"])

        # 2. Change status to in_progress
        code = main([storage_arg, "status", '--task.id', str(task_id)[:8], "-s", "in_progress"])
        assert(code == 0)
        storage = JsonStorage(json_tmp_uri)
        tasks = storage.load_tasks()
        assert(storage.task_status(tasks[0].id) == TaskStatus.in_progress)

        # 3. Set recurrence
        code = main([
            storage_arg,
            "repeat",
            '--task.id',
            str(task_id)[:8],
            "--schedule-type",
            "cron",
            "--schedule",
            "0 9 * * 1",
            "--until",
            "2026-06-26T06:26:26Z",
        ])
        assert(code == 0)
        tasks = JsonStorage(json_tmp_uri).load_tasks()
        assert(tasks[0].recurrence_rule_id is not None)

        rules = JsonStorage(json_tmp_uri).load_recurrence_rules()
        assert(len(rules) == 1)
        assert(rules[0].schedule_type == RecurrenceScheduleType.cron)
        assert(rules[0].schedule_expression == "0 9 * * 1")
        assert(rules[0].until_date is not None)

        # 4. Mark done via shorthand
        code = main([storage_arg, "done", '--task.id', str(task_id)[:8]])
        assert(code == 0)
        storage = JsonStorage(json_tmp_uri)
        tasks = storage.load_tasks()
        assert(storage.task_status(tasks[0].id) == TaskStatus.done)

        # 5. List tasks
        code = main([storage_arg, "list"])
        assert(code == 0)
