"""Unit tests for pyknic-todo CLI and storage."""

import shutil
import tempfile
import unittest
import uuid
from pathlib import Path

from pyknic_todo.cli import main
from pyknic_todo.models import RecurrenceRule, StateHistoryEvent, Task, TaskPriority, RecurrenceEndCondtionType, RecurrenceScheduleType, EndCondition, TaskStatus

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


class TestPyknicTodo(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir = Path(self.temp_dir) / "data"

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_change_status(self) -> None:
        storage = Storage(self.data_dir)
        task = Task(title="Deploy app")
        storage.append_task(task)

        updated = storage.set_task_status(str(task.id)[:8], TaskStatus.in_progress, comment="Started working")
        self.assertEqual(updated.version, 1)
        self.assertIsNone(updated.completed_at)
        self.assertEqual(storage.task_status(str(task.id)[:8]), TaskStatus.in_progress)

        done_task = storage.set_task_status(task.id, TaskStatus.done)
        self.assertEqual(storage.task_status(task.id), TaskStatus.done)
        self.assertEqual(done_task.version, 2)
        self.assertIsNotNone(done_task.completed_at)

        # Check history contains 3 events
        history = storage.load_history()
        self.assertEqual(len(history), 3)
        self.assertEqual(history[1].next_state, TaskStatus.in_progress)
        self.assertEqual(history[1].comment, "Started working")
        self.assertEqual(history[2].next_state, TaskStatus.done)

    def test_cli_end_to_end(self) -> None:
        data_arg = f"--data-dir={self.data_dir}"

        # 1. Add task via CLI
        code = main([data_arg, "add", "Write docs", "-p", "high", "-t", "docs,work"])
        self.assertEqual(code, 0)

        storage = Storage(self.data_dir)
        tasks = storage.load_tasks()
        self.assertEqual(len(tasks), 1)
        task_id = tasks[0].id
        self.assertEqual(tasks[0].title, "Write docs")
        self.assertEqual(tasks[0].priority, TaskPriority("high"))
        self.assertEqual(tasks[0].tags, ["docs", "work"])

        # 2. Change status to in_progress
        code = main([data_arg, "status", str(task_id)[:8], "in_progress"])
        self.assertEqual(code, 0)
        tasks = Storage(self.data_dir).load_tasks()
        self.assertEqual(storage.task_status(tasks[0].id), TaskStatus.in_progress)

        # 3. Set recurrence
        code = main([
            data_arg,
            "repeat",
            str(task_id)[:8],
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
        self.assertEqual(rules[0].schedule_type, RecurrenceScheduleType.cron)
        self.assertEqual(rules[0].schedule_expression, "0 9 * * 1")

        # 4. Mark done via shorthand
        code = main([data_arg, "done", str(task_id)[:8]])
        self.assertEqual(code, 0)
        storage = Storage(self.data_dir)
        tasks = storage.load_tasks()
        self.assertEqual(storage.task_status(tasks[0].id), TaskStatus.done)

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
        task = Task(
            title="Isolated task",
            description="Details",
            priority=TaskPriority("high"),
            tags=["iso"],
        )
        ts.append_task(task)
        self.assertEqual(task.title, "Isolated task")
        self.assertEqual(task.priority, TaskPriority("high"))

        # Read tasks
        tasks = ts.load_tasks()
        self.assertEqual(len(tasks), 1)

        # Document model
        doc_model = ts.load_document_model()
        self.assertEqual(len(doc_model.items), 1)

    def test_recurrence_storage_isolated(self) -> None:
        rec_dir = Path(self.temp_dir) / "rec_only"
        rs = RecurrenceRuleStorage(data_dir=rec_dir)

        # Ensure only recurrence_rules.json was created
        self.assertTrue((rec_dir / "recurrence_rules.json").exists())
        self.assertFalse((rec_dir / "tasks.json").exists())
        self.assertFalse((rec_dir / "states_history.json").exists())

        # Create rule
        rule = RecurrenceRule(
            schedule_type=RecurrenceScheduleType.rrule,
            schedule_expression="FREQ=DAILY",
            end_condition=EndCondition(
                condition_type=RecurrenceEndCondtionType.count,
                max_occurrences=5,
            )
        )
        rs.append_recurrence_rule(rule)
        self.assertEqual(rule.schedule_type, RecurrenceScheduleType.rrule)
        self.assertEqual(rule.schedule_expression, "FREQ=DAILY")
        self.assertEqual(rule.end_condition.condition_type, RecurrenceEndCondtionType.count)
        self.assertEqual(rule.end_condition.max_occurrences, 5)

        # Read rules
        rules = [x.model_dump() for x in rs.load_recurrence_rules()]
        self.assertEqual(len(rules), 1)

        # Model representation
        rule_models = rs.load_recurrence_rules()
        self.assertEqual(len(rule_models), 1)
        self.assertIsInstance(rule_models[0], RecurrenceRule)
        self.assertEqual(rule_models[0].schedule_expression, "FREQ=DAILY")

        # Document model
        doc_model = rs.load_document_model()
        self.assertEqual(len(doc_model.items), 1)

    def test_history_storage_isolated(self) -> None:
        hist_dir = Path(self.temp_dir) / "hist_only"
        hs = HistoryStorage(data_dir=hist_dir)

        # Ensure only states_history.json was created
        self.assertTrue((hist_dir / "states_history.json").exists())
        self.assertFalse((hist_dir / "tasks.json").exists())
        self.assertFalse((hist_dir / "recurrence_rules.json").exists())

        # Record event
        new_uid = uuid.uuid4()
        event = StateHistoryEvent(
            task_id=new_uid,
            next_state=TaskStatus.in_progress,
            # actor_client_id="test-client-1",
            comment="Started work",
        )
        hs.record_history_event(event)
        self.assertEqual(event.task_id, new_uid)
        self.assertEqual(event.next_state, TaskStatus.in_progress)
        # self.assertEqual(event.actor_client_id, "test-client-1")
        self.assertEqual(event.comment, "Started work")

        # Read history
        events = hs.load_history()
        self.assertEqual(len(events), 1)

        # Find by task_id
        t_events = hs.find_events_for_task(new_uid)
        self.assertEqual(len(t_events), 1)
        self.assertEqual(len(hs.find_events_for_task("t-999")), 0)

        # Model representation
        event_models = hs.load_history()
        self.assertEqual(len(event_models), 1)
        self.assertIsInstance(event_models[0], StateHistoryEvent)
        self.assertEqual(event_models[0].task_id, new_uid)

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
