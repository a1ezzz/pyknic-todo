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
    storage.create_task(title=f"Concurrent task {index}")


class TestPyknicTodo(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir = Path(self.temp_dir) / "data"

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_task_and_history(self) -> None:
        storage = Storage(self.data_dir)
        task = storage.create_task(
            title="Buy groceries",
            description="Milk, bread, apples",
            priority="high",
            status="pending",
            tags=["home", "food"],
        )

        self.assertEqual(task["title"], "Buy groceries")
        self.assertEqual(task["description"], "Milk, bread, apples")
        self.assertEqual(task["priority"], "high")
        self.assertEqual(task["status"], "pending")
        self.assertEqual(task["tags"], ["home", "food"])
        self.assertEqual(task["version"], 1)
        self.assertIsNone(task["recurrence_rule_id"])
        self.assertIsNotNone(task["created_at"])
        self.assertIsNotNone(task["updated_at"])

        # Check tasks.json structure
        with open(self.data_dir / "tasks.json", "r", encoding="utf-8") as f:
            tasks_data = json.load(f)
        self.assertEqual(tasks_data["$schema_version"], "1.0.0")
        self.assertTrue(tasks_data["client_id"].startswith("cli-"))
        self.assertEqual(len(tasks_data["items"]), 1)
        self.assertEqual(tasks_data["items"][0]["id"], task["id"])

        # Check states_history.json
        with open(self.data_dir / "states_history.json", "r", encoding="utf-8") as f:
            history_data = json.load(f)
        self.assertEqual(history_data["$schema_version"], "1.0.0")
        self.assertEqual(len(history_data["events"]), 1)
        event = history_data["events"][0]
        self.assertEqual(event["task_id"], task["id"])
        self.assertEqual(event["new_state"], {"status": "pending"})

    def test_change_status(self) -> None:
        storage = Storage(self.data_dir)
        task = storage.create_task(title="Deploy app", status="pending")

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

    def test_set_recurrence_schedule(self) -> None:
        storage = Storage(self.data_dir)
        task = storage.create_task(title="Weekly review")

        updated_task, rule = storage.set_task_recurrence(
            task_id_query=task["id"][:6],
            schedule_type="rrule",
            schedule_expression="FREQ=WEEKLY;BYDAY=MO",
            end_condition_type="count",
            max_occurrences=5,
        )

        self.assertEqual(updated_task["recurrence_rule_id"], rule["id"])
        self.assertEqual(rule["schedule_type"], "rrule")
        self.assertEqual(rule["schedule_expression"], "FREQ=WEEKLY;BYDAY=MO")
        self.assertEqual(rule["end_condition"]["type"], "count")
        self.assertEqual(rule["end_condition"]["max_occurrences"], 5)

        # Check recurrence_rules.json file
        with open(self.data_dir / "recurrence_rules.json", "r", encoding="utf-8") as f:
            rec_data = json.load(f)
        self.assertEqual(rec_data["$schema_version"], "1.0.0")
        self.assertEqual(len(rec_data["items"]), 1)
        self.assertEqual(rec_data["items"][0]["id"], rule["id"])

    def test_cli_end_to_end(self) -> None:
        data_arg = f"--data-dir={self.data_dir}"

        # 1. Add task via CLI
        code = main([data_arg, "add", "Write docs", "-p", "high", "-t", "docs,work"])
        self.assertEqual(code, 0)

        tasks = Storage(self.data_dir).load_tasks()
        self.assertEqual(len(tasks), 1)
        task_id = tasks[0]["id"]
        self.assertEqual(tasks[0]["title"], "Write docs")
        self.assertEqual(tasks[0]["priority"], "high")
        self.assertEqual(tasks[0]["tags"], ["docs", "work"])

        # 2. Change status to in_progress
        code = main([data_arg, "status", task_id[:8], "in_progress"])
        self.assertEqual(code, 0)
        tasks = Storage(self.data_dir).load_tasks()
        self.assertEqual(tasks[0]["status"], "in_progress")

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
        self.assertIsNotNone(tasks[0]["recurrence_rule_id"])

        rules = Storage(self.data_dir).load_recurrence_rules()
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]["schedule_type"], "cron")
        self.assertEqual(rules[0]["schedule_expression"], "0 9 * * 1")

        # 4. Mark done via shorthand
        code = main([data_arg, "done", task_id[:8]])
        self.assertEqual(code, 0)
        tasks = Storage(self.data_dir).load_tasks()
        self.assertEqual(tasks[0]["status"], "done")

        # 5. List tasks
        code = main([data_arg, "list"])
        self.assertEqual(code, 0)

    def test_settings_defaults(self) -> None:
        settings = Settings()
        self.assertEqual(settings.schema_version, "1.0.0")
        self.assertEqual(settings.client_id_prefix, "cli")
        self.assertEqual(settings.default_priority, "medium")
        self.assertEqual(settings.default_status, "pending")
        self.assertEqual(settings.data_dir, Path("./data"))

    def test_settings_env_override(self) -> None:
        with patch.dict(os.environ, {
            "PYKNIC_TODO_DATA_DIR": "/tmp/custom_data",
            "PYKNIC_TODO_DEFAULT_PRIORITY": "urgent",
            "PYKNIC_TODO_DEFAULT_STATUS": "new",
        }):
            settings = Settings()
            self.assertEqual(settings.data_dir, Path("/tmp/custom_data"))
            self.assertEqual(settings.default_priority, "urgent")
            self.assertEqual(settings.default_status, "new")

    def test_settings_todo_data_dir_alias(self) -> None:
        with patch.dict(os.environ, {
            "TODO_DATA_DIR": "/tmp/alias_data",
        }, clear=True):
            settings = Settings()
            self.assertEqual(settings.data_dir, Path("/tmp/alias_data"))

    def test_storage_with_custom_settings(self) -> None:
        custom_settings = Settings(
            data_dir=self.data_dir,
            schema_version="2.0.0",
            client_id_prefix="worker",
            default_priority="high",
        )
        storage = Storage(settings=custom_settings)
        task = storage.create_task(title="Custom task")
        self.assertEqual(task["priority"], "high")

        # Verify client_id and schema_version in tasks.json
        with open(self.data_dir / "tasks.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["$schema_version"], "2.0.0")
        self.assertTrue(data["client_id"].startswith("worker-"))

    def test_cli_config_command(self) -> None:
        data_arg = f"--data-dir={self.data_dir}"
        f = io.StringIO()
        with patch("sys.stdout", f):
            code = main([data_arg, "config"])
        self.assertEqual(code, 0)
        output = f.getvalue()
        self.assertIn("data_dir:", output)
        self.assertIn("schema_version: 1.0.0", output)

        f_json = io.StringIO()
        with patch("sys.stdout", f_json):
            code = main([data_arg, "config", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(f_json.getvalue())
        self.assertEqual(data["schema_version"], "1.0.0")
        self.assertEqual(data["default_priority"], "medium")

    def test_cli_uses_custom_settings(self) -> None:
        settings = Settings(
            data_dir=self.data_dir,
            default_priority="urgent",
        )
        code = main(["add", "Urgent by default"], settings=settings)
        self.assertEqual(code, 0)
        tasks = Storage(settings=settings).load_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["priority"], "urgent")

    def test_flock_called_on_create_and_load(self) -> None:
        storage = Storage(self.data_dir)
        with patch("fcntl.flock", wraps=None) as mock_flock:
            storage.create_task("Test task with flock")
            self.assertTrue(mock_flock.called)

    def test_flock_nested_reentrancy(self) -> None:
        storage = Storage(self.data_dir)
        with storage.lock(exclusive=True):
            self.assertEqual(storage._lock_depth, 1)
            self.assertTrue(storage._lock_is_exclusive)
            with storage.lock(exclusive=False):
                self.assertEqual(storage._lock_depth, 2)
                with storage.lock(exclusive=True):
                    self.assertEqual(storage._lock_depth, 3)
                self.assertEqual(storage._lock_depth, 2)
            self.assertEqual(storage._lock_depth, 1)
        self.assertEqual(storage._lock_depth, 0)
        self.assertIsNone(storage._lock_fd)

    def test_flock_blocking_conflict_on_same_dir(self) -> None:
        storage1 = Storage(self.data_dir)
        storage2 = Storage(self.data_dir)

        with storage1.lock(exclusive=True):
            with self.assertRaises((BlockingIOError, OSError)):
                with storage2.lock(exclusive=True, blocking=False):
                    pass

    def test_flock_different_directories_independent(self) -> None:
        other_dir = Path(self.temp_dir) / "data_other"
        storage1 = Storage(self.data_dir)
        storage2 = Storage(other_dir)

        with storage1.lock(exclusive=True):
            # Should be able to acquire lock on other_dir without conflict
            with storage2.lock(exclusive=True, blocking=False):
                storage2.create_task("Independent task")

        tasks2 = storage2.load_tasks()
        self.assertEqual(len(tasks2), 1)
        self.assertEqual(tasks2[0]["title"], "Independent task")

    def test_flock_concurrent_creates_no_lost_updates(self) -> None:
        procs = [
            multiprocessing.Process(
                target=_concurrent_create_worker,
                args=(str(self.data_dir), i),
            )
            for i in range(10)
        ]
        for p in procs:
            p.start()
        for p in procs:
            p.join()

        storage = Storage(self.data_dir)
        tasks = storage.load_tasks()
        self.assertEqual(len(tasks), 10)
        history = storage.load_history()
        self.assertEqual(len(history), 10)

    def test_list_default_hides_completed_and_deleted(self) -> None:
        data_arg = f"--data-dir={self.data_dir}"
        storage = Storage(self.data_dir)
        t_pending = storage.create_task(title="Pending task", status="pending")
        t_in_progress = storage.create_task(title="In progress task", status="in_progress")
        storage.create_task(title="Done task", status="done")
        storage.create_task(title="Deleted task", status="deleted")

        f_out = io.StringIO()
        with patch("sys.stdout", f_out):
            code = main([data_arg, "list", "--json"])
        self.assertEqual(code, 0)
        listed = json.loads(f_out.getvalue())
        self.assertEqual(len(listed), 2)
        listed_ids = {t["id"] for t in listed}
        self.assertEqual(listed_ids, {t_pending["id"], t_in_progress["id"]})

        # Table output check
        f_table = io.StringIO()
        with patch("sys.stdout", f_table):
            code = main([data_arg, "list"])
        self.assertEqual(code, 0)
        table_text = f_table.getvalue()
        self.assertIn("Pending task", table_text)
        self.assertIn("In progress task", table_text)
        self.assertNotIn("Done task", table_text)
        self.assertNotIn("Deleted task", table_text)

    def test_list_all_flag_shows_all_tasks(self) -> None:
        data_arg = f"--data-dir={self.data_dir}"
        storage = Storage(self.data_dir)
        storage.create_task(title="Pending task", status="pending")
        storage.create_task(title="Done task", status="done")
        storage.create_task(title="Deleted task", status="deleted")

        # Test --all
        f_out = io.StringIO()
        with patch("sys.stdout", f_out):
            code = main([data_arg, "list", "--all", "--json"])
        self.assertEqual(code, 0)
        listed = json.loads(f_out.getvalue())
        self.assertEqual(len(listed), 3)

        # Test -a shorthand
        f_short = io.StringIO()
        with patch("sys.stdout", f_short):
            code = main([data_arg, "list", "-a", "--json"])
        self.assertEqual(code, 0)
        listed_short = json.loads(f_short.getvalue())
        self.assertEqual(len(listed_short), 3)

        # Test --all in table output
        f_table = io.StringIO()
        with patch("sys.stdout", f_table):
            code = main([data_arg, "list", "--all"])
        self.assertEqual(code, 0)
        table_text = f_table.getvalue()
        self.assertIn("Pending task", table_text)
        self.assertIn("Done task", table_text)
        self.assertIn("Deleted task", table_text)

    def test_list_completed_modes(self) -> None:
        data_arg = f"--data-dir={self.data_dir}"
        storage = Storage(self.data_dir)
        storage.create_task(title="Pending task", status="pending")
        t_done = storage.create_task(title="Done task", status="done")

        # --completed flag
        f_out = io.StringIO()
        with patch("sys.stdout", f_out):
            code = main([data_arg, "list", "--completed", "--json"])
        self.assertEqual(code, 0)
        listed = json.loads(f_out.getvalue())
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["id"], t_done["id"])

        # -c shorthand
        f_short = io.StringIO()
        with patch("sys.stdout", f_short):
            code = main([data_arg, "list", "-c", "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(f_short.getvalue())), 1)

        # --mode completed
        f_mode = io.StringIO()
        with patch("sys.stdout", f_mode):
            code = main([data_arg, "list", "--mode", "completed", "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(f_mode.getvalue())), 1)

        # --mode all
        f_mode_all = io.StringIO()
        with patch("sys.stdout", f_mode_all):
            code = main([data_arg, "list", "--mode", "all", "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(f_mode_all.getvalue())), 2)

    def test_list_status_filter_direct(self) -> None:
        data_arg = f"--data-dir={self.data_dir}"
        storage = Storage(self.data_dir)
        storage.create_task(title="Task 1", status="pending")
        storage.create_task(title="Task 2", status="done")

        f_out = io.StringIO()
        with patch("sys.stdout", f_out):
            code = main([data_arg, "list", "-s", "done", "--json"])
        self.assertEqual(code, 0)
        listed = json.loads(f_out.getvalue())
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["title"], "Task 2")

    def test_task_storage_isolated(self) -> None:
        task_dir = Path(self.temp_dir) / "tasks_only"
        ts = TaskStorage(data_dir=task_dir)

        # Ensure only tasks.json was created
        self.assertTrue((task_dir / "tasks.json").exists())
        self.assertFalse((task_dir / "recurrence_rules.json").exists())
        self.assertFalse((task_dir / "states_history.json").exists())

        # Create task
        task = ts.create_task(
            title="Isolated task",
            description="Details",
            priority="high",
            status="pending",
            tags=["iso"],
        )
        self.assertEqual(task["title"], "Isolated task")
        self.assertEqual(task["priority"], "high")

        # Read tasks
        tasks = ts.load_tasks()
        self.assertEqual(len(tasks), 1)

        # Document model
        doc_model = ts.load_document_model()
        self.assertEqual(len(doc_model.items), 1)

        # Find task
        found = ts.find_task(task["id"])
        self.assertIsNotNone(found)
        assert found is not None
        self.assertEqual(found["id"], task["id"])

        # Update status
        updated = ts.set_task_status(task["id"], "done")
        self.assertEqual(updated["status"], "done")
        self.assertIsNotNone(updated["completed_at"])

        # Update recurrence rule ID
        with_rec = ts.set_recurrence_rule_id(task["id"], "rec-123")
        self.assertEqual(with_rec["recurrence_rule_id"], "rec-123")

        # Validation errors
        with self.assertRaises(ValueError):
            ts.create_task(title="Bad", status="invalid_status")
        with self.assertRaises(ValueError):
            ts.create_task(title="Bad", priority="invalid_priority")
        with self.assertRaises(KeyError):
            ts.set_task_status("nonexistent_id", "done")

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

        ts = StorageFactory.create_task_storage("json", data_dir=self.data_dir)
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
            StorageFactory.create_task_storage("nonexistent_backend")
        with self.assertRaises(ValueError):
            StorageFactory.create_recurrence_storage("nonexistent_backend")
        with self.assertRaises(ValueError):
            StorageFactory.create_history_storage("nonexistent_backend")

    def test_cli_storage_type_argument(self) -> None:
        data_arg = f"--data-dir={self.data_dir}"
        f_out = io.StringIO()
        with patch("sys.stdout", f_out):
            code = main([data_arg, "--storage-type=json", "add", "CLI storage type task"])
        self.assertEqual(code, 0)
        self.assertIn("Task created:", f_out.getvalue())


if __name__ == "__main__":
    unittest.main()
