"""Unit tests for pyknic-todo CLI and storage."""

import io
import json
from unittest.mock import patch

import pytest
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

        # 5. Show task details (without history)
        code = main([storage_arg, "show", '--task.id', str(task_id)[:8]])
        assert(code == 0)

        # Show by title
        code = main([storage_arg, "show", '--task.title', "Write docs"])
        assert(code == 0)

        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = main([storage_arg, "--json-mode", "show", '--task.id', str(task_id)[:8]])
        assert(code == 0)
        show_data = json.loads(buf.getvalue())
        kv = show_data["kv_result"]
        assert(kv["id"] == str(task_id))
        assert(kv["title"] == "Write docs")
        assert(kv["status"] == TaskStatus.done.value)
        assert(kv["priority"] == TaskPriority.high.value)
        assert(kv["tags"] == ["docs", "work"])
        assert(kv["recurrence"] is not None)
        assert("history" not in kv)

        # Show non-existent task
        with pytest.raises(ValueError, match="Unable to find a matching task"):
            main([storage_arg, "show", '--task.id', "00000000"])

        # 6. Show task status history via history subcommand
        code = main([storage_arg, "history", '--task.id', str(task_id)[:8]])
        assert(code == 0)

        # History by title
        code = main([storage_arg, "history", '--task.title', "Write docs"])
        assert(code == 0)

        # History with explicit depth
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = main([storage_arg, "--json-mode", "history", '--task.id', str(task_id)[:8], "--depth", "2"])
        assert(code == 0)
        hist_data = json.loads(buf.getvalue())
        table = hist_data["table_result"]
        assert(len(table["status"]) == 2)
        assert(table["status"][-1] == TaskStatus.done.value)
        assert(table["status"][-2] == TaskStatus.in_progress.value)

        # History with history-depth alias and depth 1
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = main([storage_arg, "--json-mode", "history", '--task.id', str(task_id)[:8], "--history-depth", "1"])
        assert(code == 0)
        hist_data = json.loads(buf.getvalue())
        assert(len(hist_data["table_result"]["status"]) == 1)
        assert(hist_data["table_result"]["status"][0] == TaskStatus.done.value)

        # History with -d alias and depth 0
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = main([storage_arg, "--json-mode", "history", '--task.id', str(task_id)[:8], "-d", "0"])
        assert(code == 0)
        hist_data = json.loads(buf.getvalue())
        assert(len(hist_data["table_result"]["status"]) == 0)

        # History for non-existent task
        with pytest.raises(ValueError, match="Unable to find a matching task"):
            main([storage_arg, "history", '--task.id', "00000000"])

        # 7. List tasks
        code = main([storage_arg, "list"])
        assert(code == 0)

        # 8. List unknown project task
        code = main([storage_arg, "list", "--project", "unknown-project"])
        assert(code == 0)

        # 9. Delete a task
        code = main([storage_arg, "delete", '--task.id', str(task_id)[:8]])
        assert(code == 0)
        storage = JsonStorage(json_tmp_uri)
        tasks = storage.load_tasks()
        assert(storage.task_status(tasks[0].id) == TaskStatus.deleted)

    def test_cli_show_details_and_ambiguity(self, json_tmp_uri: URI) -> None:
        storage_arg = f"--storage-uri={str(json_tmp_uri)}"

        # Add two tasks with identical titles
        main([storage_arg, "add", "-t", "Same Title"])
        main([storage_arg, "add", "-t", "Same Title"])

        # Ambiguous title match raises ValueError
        with pytest.raises(ValueError, match="Multiple tasks spotted!"):
            main([storage_arg, "show", '--task.title', "Same Title"])

        with pytest.raises(ValueError, match="Multiple tasks spotted!"):
            main([storage_arg, "history", '--task.title', "Same Title"])

        # Show task with comments in status
        tasks = JsonStorage(json_tmp_uri).load_tasks()
        t1_id = str(tasks[0].id)

        main([storage_arg, "status", '--task.id', t1_id[:8], "-s", "in_progress", "--comment", "Starting work"])
        main([storage_arg, "status", '--task.id', t1_id[:8], "-s", "cancelled", "--comment", "No longer needed"])

        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = main([storage_arg, "--json-mode", "show", '--task.id', t1_id[:8]])
        assert(code == 0)
        show_data = json.loads(buf.getvalue())
        kv = show_data["kv_result"]
        assert(kv["status"] == TaskStatus.cancelled.value)
        assert("history" not in kv)
        assert(kv["recurrence"] is None)

        # Check history subcommand receives comments
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = main([storage_arg, "--json-mode", "history", '--task.id', t1_id[:8], "--depth", "10"])
        assert(code == 0)
        hist_data = json.loads(buf.getvalue())
        tbl = hist_data["table_result"]
        assert(len(tbl["status"]) == 3)
        assert(tbl["comment"][1] == "Starting work")
        assert(tbl["comment"][2] == "No longer needed")

    def test_cli_list_full_id_and_repeating(self, json_tmp_uri: URI) -> None:
        storage_arg = f"--storage-uri={str(json_tmp_uri)}"

        main([storage_arg, "add", "-t", "Repeating Task"])
        main([storage_arg, "add", "-t", "One-off Task"])

        storage = JsonStorage(json_tmp_uri)
        tasks = storage.load_tasks()
        t_repeat = next(t for t in tasks if t.title == "Repeating Task")
        t_oneoff = next(t for t in tasks if t.title == "One-off Task")

        main([
            storage_arg,
            "repeat",
            "--task.id",
            str(t_repeat.id)[:8],
            "--schedule-type",
            "cron",
            "--schedule",
            "0 9 * * 1",
        ])

        # Default list: short 8-char IDs, repeating column
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = main([storage_arg, "--json-mode", "list"])
        assert(code == 0)
        data = json.loads(buf.getvalue())
        tbl = data["table_result"]

        assert("repeating" in tbl)
        assert("id" in tbl)

        # Map by title
        items = {
            tbl["title"][i]: (tbl["id"][i], tbl["repeating"][i])
            for i in range(len(tbl["title"]))
        }
        assert(items["Repeating Task"][0] == str(t_repeat.id)[:8])
        assert(items["Repeating Task"][1] is True)
        assert(len(items["Repeating Task"][0]) == 8)

        assert(items["One-off Task"][0] == str(t_oneoff.id)[:8])
        assert(items["One-off Task"][1] is False)
        assert(len(items["One-off Task"][0]) == 8)

        # List with --full-id
        buf_full = io.StringIO()
        with patch("sys.stdout", buf_full):
            code = main([storage_arg, "--json-mode", "list", "--full-id"])
        assert(code == 0)
        data_full = json.loads(buf_full.getvalue())
        tbl_full = data_full["table_result"]

        items_full = {
            tbl_full["title"][i]: (tbl_full["id"][i], tbl_full["repeating"][i])
            for i in range(len(tbl_full["title"]))
        }
        assert(items_full["Repeating Task"][0] == str(t_repeat.id))
        assert(items_full["Repeating Task"][1] is True)
        assert(len(items_full["Repeating Task"][0]) == 36)

        assert(items_full["One-off Task"][0] == str(t_oneoff.id))
        assert(items_full["One-off Task"][1] is False)
        assert(len(items_full["One-off Task"][0]) == 36)

        # Table output check (non-json mode)
        buf_table = io.StringIO()
        with patch("sys.stdout", buf_table):
            code = main([storage_arg, "list"])
        assert(code == 0)
        assert(str(t_repeat.id)[:8] in buf_table.getvalue())
        assert(str(t_repeat.id)[:14] not in buf_table.getvalue())

        buf_table_full = io.StringIO()
        with patch("sys.stdout", buf_table_full):
            code = main([storage_arg, "list", "--full-id"])
        assert(code == 0)
        assert(str(t_repeat.id)[:14] in buf_table_full.getvalue())
