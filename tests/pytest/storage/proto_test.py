"""Unit tests for pyknic-todo CLI and storage."""

import io
import json
import multiprocessing
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pyknic_todo.cli import main
from pyknic_todo.models import RecurrenceRule, StateHistoryEvent, Task
from pyknic_todo.settings import Settings
from pyknic_todo.storage.storage import (
    AbstractHistoryStorage,
    AbstractRecurrenceRuleStorage,
    AbstractStorage,
    AbstractTaskStorage,
    HistoryStorage,
    JsonHistoryStorage,
    JsonRecurrenceRuleStorage,
    JsonStorage,
    JsonTaskStorage,
    RecurrenceRuleStorage,
    Storage,
    StorageFactory,
    TaskStorage,
)


def _concurrent_create_worker(data_dir_str: str, index: int) -> None:
    storage = Storage(data_dir_str)
    storage.append_task(title=f"Concurrent task {index}")


class TestPyknicTodo(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir = Path(self.temp_dir) / "data"

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_change_status(self) -> None:
        storage = Storage(self.data_dir)
        task = storage.append_task(title="Deploy app", status="pending")

        updated = storage.set_task_status(task["id"][:8], "in_progress", comment="Started working")
        self.assertEqual(updated["status"], "in_progress")
        self.assertEqual(updated["version"], 2)
        self.assertIsNone(updated["completed_at"])

        done_task = storage.set_task_status(task["id"], "done")
        self.assertEqual(done_task["status"], "done")
        self.assertEqual(done_task["version"], 3)
        self.assertIsNotNone(done_task["completed_at"])

        # Check history contains 3 events
        history = storage.load_history()
        self.assertEqual(len(history), 3)
        self.assertEqual(history[1]["new_state"]["status"], "in_progress")
        self.assertEqual(history[1]["comment"], "Started working")
        self.assertEqual(history[2]["new_state"]["status"], "done")

    def test_cli_end_to_end(self) -> None:
        data_arg = f"--data-dir={self.data_dir}"

        # 1. Add task via CLI
        code = main([data_arg, "add", "Write docs", "-p", "high", "-t", "docs,work"])
        self.assertEqual(code, 0)

        tasks = Storage(self.data_dir).load_tasks()
        self.assertEqual(len(tasks), 1)
        task_id = tasks[0].id
        self.assertEqual(tasks[0].title, "Write docs")
        self.assertEqual(tasks[0].priority, "high")
        self.assertEqual(tasks[0].tags, ["docs", "work"])

        # 2. Change status to in_progress
        code = main([data_arg, "status", task_id[:8], "in_progress"])
        self.assertEqual(code, 0)
        tasks = Storage(self.data_dir).load_tasks()
        self.assertEqual(tasks[0].status, "in_progress")

        # 3. Set recurrence
        code = main([
            data_arg,
            "repeat",
            task_id[:8],
            "--type",
            "cron",
            "-e",
            "0 9 * * 1",
            "--end-type",
            "never",
        ])
        self.assertEqual(code, 0)
        tasks = Storage(self.data_dir).load_tasks()
        self.assertIsNotNone(tasks[0].recurrence_rule_id)

        rules = Storage(self.data_dir).load_recurrence_rules()
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]["schedule_type"], "cron")
        self.assertEqual(rules[0]["schedule_expression"], "0 9 * * 1")

        # 4. Mark done via shorthand
        code = main([data_arg, "done", task_id[:8]])
        self.assertEqual(code, 0)
        tasks = Storage(self.data_dir).load_tasks()
        self.assertEqual(tasks[0].status, "done")

        # 5. List tasks
        code = main([data_arg, "list"])
        self.assertEqual(code, 0)

    def test_task_storage_isolated(self) -> None:
        task_dir = Path(self.temp_dir) / "tasks_only"
        ts = TaskStorage(data_dir=task_dir)

        # Ensure only tasks.json was created
        self.assertTrue((task_dir / "tasks.json").exists())
        self.assertFalse((task_dir / "recurrence_rules.json").exists())
        self.assertFalse((task_dir / "states_history.json").exists())

        # Create task
        task = ts.append_task(
            title="Isolated task",
            description="Details",
            priority="high",
            status="pending",
            tags=["iso"],
        ).model_dump()
        self.assertEqual(task["title"], "Isolated task")
        self.assertEqual(task["priority"], "high")

        # Read tasks
        tasks = ts.load_tasks()
        self.assertEqual(len(tasks), 1)

        # Document model
        doc_model = ts.load_document_model()
        self.assertEqual(len(doc_model.items), 1)

        # Validation errors
        with self.assertRaises(ValueError):
            ts.append_task(title="Bad", status="invalid_status", priority="low")
        with self.assertRaises(ValueError):
            ts.append_task(title="Bad", status="new", priority="invalid_priority")

    def test_recurrence_storage_isolated(self) -> None:
        rec_dir = Path(self.temp_dir) / "rec_only"
        rs = RecurrenceRuleStorage(data_dir=rec_dir)

        # Ensure only recurrence_rules.json was created
        self.assertTrue((rec_dir / "recurrence_rules.json").exists())
        self.assertFalse((rec_dir / "tasks.json").exists())
        self.assertFalse((rec_dir / "states_history.json").exists())

        # Create rule
        rule = rs.create_rule(
            schedule_type="rrule",
            schedule_expression="FREQ=DAILY",
            end_condition_type="count",
            max_occurrences=5,
        )
        self.assertEqual(rule["schedule_type"], "rrule")
        self.assertEqual(rule["schedule_expression"], "FREQ=DAILY")
        self.assertEqual(rule["end_condition"]["type"], "count")
        self.assertEqual(rule["end_condition"]["max_occurrences"], 5)

        # Read rules
        rules = rs.load_rules()
        self.assertEqual(len(rules), 1)

        # Model representation
        rule_models = rs.load_rule_models()
        self.assertEqual(len(rule_models), 1)
        self.assertIsInstance(rule_models[0], RecurrenceRule)
        self.assertEqual(rule_models[0].schedule_expression, "FREQ=DAILY")

        # Document model
        doc_model = rs.load_document_model()
        self.assertEqual(len(doc_model.items), 1)

        # Find rule
        found = rs.find_rule(rule["id"])
        self.assertIsNotNone(found)
        assert found is not None
        self.assertEqual(found["id"], rule["id"])

        found_model = rs.find_rule_model(rule["id"])
        self.assertIsNotNone(found_model)
        assert found_model is not None
        self.assertEqual(found_model.id, rule["id"])

        # Validation errors
        with self.assertRaises(ValueError):
            rs.create_rule(schedule_type="invalid", schedule_expression="FREQ=DAILY")
        with self.assertRaises(ValueError):
            rs.create_rule(schedule_type="rrule", schedule_expression="FREQ=DAILY", end_condition_type="invalid")

    def test_history_storage_isolated(self) -> None:
        hist_dir = Path(self.temp_dir) / "hist_only"
        hs = HistoryStorage(data_dir=hist_dir)

        # Ensure only states_history.json was created
        self.assertTrue((hist_dir / "states_history.json").exists())
        self.assertFalse((hist_dir / "tasks.json").exists())
        self.assertFalse((hist_dir / "recurrence_rules.json").exists())

        # Record event
        event = hs.record_event(
            task_id="t-100",
            new_state={"status": "in_progress"},
            actor_client_id="test-client-1",
            comment="Started work",
        )
        self.assertEqual(event["task_id"], "t-100")
        self.assertEqual(event["new_state"]["status"], "in_progress")
        self.assertEqual(event["actor_client_id"], "test-client-1")
        self.assertEqual(event["comment"], "Started work")

        # Read history
        events = hs.load_history()
        self.assertEqual(len(events), 1)

        # Find by task_id
        t_events = hs.find_events_for_task("t-100")
        self.assertEqual(len(t_events), 1)
        self.assertEqual(len(hs.find_events_for_task("t-999")), 0)

        # Model representation
        event_models = hs.load_event_models()
        self.assertEqual(len(event_models), 1)
        self.assertIsInstance(event_models[0], StateHistoryEvent)
        self.assertEqual(event_models[0].task_id, "t-100")

        # Document model
        doc_model = hs.load_document_model()
        self.assertEqual(len(doc_model.events), 1)

    def test_abstract_interfaces_and_json_subclasses(self) -> None:
        self.assertTrue(issubclass(JsonTaskStorage, AbstractTaskStorage))
        self.assertTrue(issubclass(JsonRecurrenceRuleStorage, AbstractRecurrenceRuleStorage))
        self.assertTrue(issubclass(JsonHistoryStorage, AbstractHistoryStorage))
        self.assertTrue(issubclass(JsonStorage, AbstractStorage))

        storage = Storage(self.data_dir)
        self.assertIsInstance(storage, AbstractStorage)
        self.assertIsInstance(storage.tasks, AbstractTaskStorage)
        self.assertIsInstance(storage.recurrence_rules, AbstractRecurrenceRuleStorage)
        self.assertIsInstance(storage.history, AbstractHistoryStorage)

    def test_storage_factory(self) -> None:
        self.assertIn("json", StorageFactory.get_registered_types())

        # Create components via factory
        st = StorageFactory.create_storage("json", data_dir=self.data_dir)
        self.assertIsInstance(st, AbstractStorage)
        self.assertIsInstance(st, JsonStorage)

        ts = StorageFactory.append_task_storage("json", data_dir=self.data_dir)
        self.assertIsInstance(ts, AbstractTaskStorage)
        self.assertIsInstance(ts, JsonTaskStorage)

        rs = StorageFactory.create_recurrence_storage("json", data_dir=self.data_dir)
        self.assertIsInstance(rs, AbstractRecurrenceRuleStorage)
        self.assertIsInstance(rs, JsonRecurrenceRuleStorage)

        hs = StorageFactory.create_history_storage("json", data_dir=self.data_dir)
        self.assertIsInstance(hs, AbstractHistoryStorage)
        self.assertIsInstance(hs, JsonHistoryStorage)

        # Factory error for unsupported backend
        with self.assertRaises(ValueError):
            StorageFactory.create_storage("nonexistent_backend")
        with self.assertRaises(ValueError):
            StorageFactory.append_task_storage("nonexistent_backend")
        with self.assertRaises(ValueError):
            StorageFactory.create_recurrence_storage("nonexistent_backend")
        with self.assertRaises(ValueError):
            StorageFactory.create_history_storage("nonexistent_backend")
