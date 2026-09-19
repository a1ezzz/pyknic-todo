
import uuid

import pytest

from pyknic_todo.storage.proto import ToDoStorageProto
from pyknic_todo.models import Task, RecurrenceRule, StateUpdatedEvent, TaskStatus, RecurrenceScheduleType

from pyknic_todo.storage.plain import TaskStorageUpdaterContextProto, PlainTaskStorageProto
from pyknic_todo.storage.plain import PlainRecurrenceRuleStorageProto, PlainStateHistoryStorageProto
from pyknic_todo.storage.plain import PlainStorageProto, PlainSettingsStorageProto

from fixtures.test_storage import InMemoryStorage


def test_abstract() -> None:
    pytest.raises(TypeError, TaskStorageUpdaterContextProto)
    pytest.raises(NotImplementedError, TaskStorageUpdaterContextProto.__call__, None)  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, TaskStorageUpdaterContextProto.commit, None)  # type: ignore[call-overload]
    # it is ok to call the following methods -- they does nothing special
    TaskStorageUpdaterContextProto.__enter__(None)  # type: ignore[type-var]
    TaskStorageUpdaterContextProto.__exit__(None, None, None, None)  # type: ignore[arg-type]

    pytest.raises(TypeError, PlainTaskStorageProto)
    pytest.raises(NotImplementedError, PlainTaskStorageProto.load_tasks, None)  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, PlainTaskStorageProto.save_tasks, None, [])  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, PlainTaskStorageProto.updater_context, None, 'id')  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, PlainTaskStorageProto.append_task, None, None)  # type: ignore[call-overload]

    pytest.raises(TypeError, PlainRecurrenceRuleStorageProto)
    with pytest.raises(NotImplementedError):
        PlainRecurrenceRuleStorageProto.load_recurrence_rules(None)  # type: ignore[arg-type]
    with pytest.raises(NotImplementedError):
        PlainRecurrenceRuleStorageProto.save_recurrence_rules(None, [])  # type: ignore[arg-type]
    with pytest.raises(NotImplementedError):
        PlainRecurrenceRuleStorageProto.append_recurrence_rule(None, None)  # type: ignore[arg-type]

    pytest.raises(TypeError, PlainStateHistoryStorageProto)
    pytest.raises(NotImplementedError, PlainStateHistoryStorageProto.load_history, None)  # type: ignore[call-overload]
    with pytest.raises(NotImplementedError):
        PlainStateHistoryStorageProto.record_history_event(None, None)  # type: ignore[arg-type]

    pytest.raises(TypeError, PlainSettingsStorageProto)
    pytest.raises(NotImplementedError, PlainSettingsStorageProto.storage_id, None)  # type: ignore[call-overload]

    pytest.raises(TypeError, PlainStorageProto)
    pytest.raises(NotImplementedError, PlainStorageProto._tasks, None)  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, PlainStorageProto._recurrence_rules, None)  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, PlainStorageProto._history, None)  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, PlainStorageProto._settings, None)  # type: ignore[call-overload]


class TestPlainStorageProto:

    def test(self) -> None:
        storage = InMemoryStorage()
        assert(isinstance(storage, PlainStorageProto))
        assert(isinstance(storage, ToDoStorageProto))

    def test_task(self) -> None:
        storage = InMemoryStorage()
        task1 = Task(title='foo')
        task2 = Task(title='bar')

        assert(storage.load_tasks() == [])

        storage.save_tasks([task1])
        assert(storage.load_tasks() == [task1])

        storage.save_tasks([])
        assert(storage.load_tasks() == [])

        storage.save_tasks([task1, task2])
        assert(storage.load_tasks() == [task1, task2])

    def test_recurrence_rule(self) -> None:
        # there is no need for a real task to save a rule

        storage = InMemoryStorage()

        rule1 = RecurrenceRule(
            schedule_type=RecurrenceScheduleType.cron,
            schedule_expression="0 9 * * 1",
        )
        rule2 = RecurrenceRule(
            schedule_type=RecurrenceScheduleType.rrule,
            schedule_expression="FREQ=DAILY",
        )

        assert(storage.load_recurrence_rules() == [])

        storage.save_recurrence_rules([rule1])
        assert(storage.load_recurrence_rules() == [rule1])

        storage.save_recurrence_rules([])
        assert(storage.load_recurrence_rules() == [])

        storage.save_recurrence_rules([rule1, rule2])
        assert(storage.load_recurrence_rules() == [rule1, rule2])

    def test_history(self) -> None:
        # there is no need for a real task to save an event

        storage = InMemoryStorage()

        event1 = StateUpdatedEvent(
            task_id=uuid.uuid4(),
            next_state=TaskStatus.in_progress
        )

        event2 = StateUpdatedEvent(
            task_id=uuid.uuid4(),
            next_state=TaskStatus.done
        )

        assert(storage.load_history() == [])

        storage.record_history_event(event1)
        assert(storage.load_history() == [event1])

        storage.record_history_event(event2)
        assert(storage.load_history() == [event1, event2])

    def test_append_task(self) -> None:
        storage = InMemoryStorage()
        task1 = Task(title='foo')
        assert(task1.version == 1)

        assert(storage.load_tasks() == [])
        assert(storage.load_recurrence_rules() == [])
        assert(storage.load_history() == [])

        pytest.raises(KeyError, storage.task_status, task1.id)

        storage.append_task(task1)
        assert(task1.version == 1)
        assert(task1.completed_at is None)
        assert(task1.deleted_at is None)
        assert(storage.load_tasks() == [task1])
        assert(storage.load_recurrence_rules() == [])
        history = storage.load_history()
        assert(len(history) == 1)
        assert(history[0].task_id == task1.id)
        assert(history[0].next_state == TaskStatus.new)

        assert(storage.task_status(task1.id) == TaskStatus.new)

    def test_task_status(self) -> None:
        storage = InMemoryStorage()
        task1 = Task(title='foo')
        assert(len(storage.load_history()) == 0)

        pytest.raises(KeyError, storage.task_status, 'invalid-id')

        storage.append_task(task1)
        assert(len(storage.load_history()) == 1)
        assert(task1.version == 1)
        assert(storage.task_status(task1.id) == TaskStatus.new)

        storage.set_task_status(task1.id, TaskStatus.in_progress)
        assert(len(storage.load_history()) == 2)
        assert(storage.task_status(task1.id) == TaskStatus.in_progress)
        assert(task1.version == 1)

        storage.set_task_status(task1.id, TaskStatus.done)
        assert(len(storage.load_history()) == 3)
        assert(storage.task_status(task1.id) == TaskStatus.done)
        assert(task1.completed_at is not None)
        assert(task1.deleted_at is None)
        assert(task1.version == 2)

        storage.set_task_status(task1.id, TaskStatus.deleted)
        assert(len(storage.load_history()) == 4)
        assert(storage.task_status(task1.id) == TaskStatus.deleted)
        assert(task1.completed_at is not None)
        assert(task1.deleted_at is not None)
        assert(task1.version == 3)

        storage.set_task_status(task1.id, TaskStatus.pending)
        assert(len(storage.load_history()) == 5)
        assert(storage.task_status(task1.id) == TaskStatus.pending)
        assert(task1.completed_at is None)
        assert(task1.deleted_at is None)
        assert(task1.version == 4)

        storage.set_task_status(task1.id, TaskStatus.done)
        assert(len(storage.load_history()) == 6)
        assert(storage.task_status(task1.id) == TaskStatus.done)
        assert(task1.completed_at is not None)
        assert(task1.deleted_at is None)
        assert(task1.version == 5)

        storage.set_task_status(task1.id, TaskStatus.cancelled)
        assert(len(storage.load_history()) == 7)
        assert(storage.task_status(task1.id) == TaskStatus.cancelled)
        assert(task1.completed_at is None)
        assert(task1.deleted_at is None)
        assert(task1.version == 6)

    def test_task_recurrence(self) -> None:
        storage = InMemoryStorage()
        task1 = Task(title='foo')
        storage.append_task(task1)

        assert(storage.load_recurrence_rules() == [])
        rule1 = RecurrenceRule(
            schedule_type=RecurrenceScheduleType.rrule,
            schedule_expression="FREQ=DAILY"
        )
        storage.set_task_recurrence(task1.id, rule1)

        assert(storage.load_recurrence_rules() == [rule1])
        assert(task1.recurrence_rule_id == rule1.id)

        storage.set_task_recurrence(task1.id)
        assert(storage.load_recurrence_rules() == [rule1])  # there is no auto-clean
        assert(task1.recurrence_rule_id is None)
