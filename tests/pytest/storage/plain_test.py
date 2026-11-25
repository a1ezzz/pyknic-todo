
import datetime
import uuid

import pytest

from pyknic_todo.storage.proto import ToDoStorageProto
from pyknic_todo.models import Task, RecurrenceRule, StateUpdatedEvent, TaskStatus, RecurrenceScheduleType

from pyknic_todo.storage.plain import PlainTaskStorageProto, PlainRecurrenceRuleStorageProto
from pyknic_todo.storage.plain import PlainStateHistoryStorageProto, PlainStorageProto
from pyknic_todo.storage.plain import PlainSettingsStorageProto
from pyknic_todo.storage.helpers import exact_one_task

from fixtures.test_storage import InMemoryStorage


def test_abstract() -> None:

    pytest.raises(TypeError, PlainTaskStorageProto)
    pytest.raises(NotImplementedError, PlainTaskStorageProto.load_tasks, None)  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, PlainTaskStorageProto.record_task, None, None)  # type: ignore[call-overload]

    pytest.raises(TypeError, PlainRecurrenceRuleStorageProto)
    with pytest.raises(NotImplementedError):
        PlainRecurrenceRuleStorageProto.load_recurrence_rules(None)  # type: ignore[arg-type]
    with pytest.raises(NotImplementedError):
        PlainRecurrenceRuleStorageProto.record_recurrence_rule(None, None)  # type: ignore[arg-type]

    pytest.raises(TypeError, PlainStateHistoryStorageProto)
    with pytest.raises(NotImplementedError):
        PlainStateHistoryStorageProto.load_states_history(None)  # type: ignore[arg-type]
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

        storage.record_task(task1)
        assert(storage.load_tasks() == [task1])

        storage.record_task(task2)
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

        storage.record_recurrence_rule(rule1)
        assert(storage.load_recurrence_rules() == [rule1])

        storage.record_recurrence_rule(rule2)
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

        assert(storage.load_states_history() == [])

        storage.record_history_event(event1)
        assert(storage.load_states_history() == [event1])

        storage.record_history_event(event2)
        assert(storage.load_states_history() == [event1, event2])

    def test_append_task(self) -> None:
        storage = InMemoryStorage()
        task1 = Task(title='foo')
        assert(task1.version == 1)

        assert(storage.load_tasks() == [])
        assert(storage.load_recurrence_rules() == [])
        assert(storage.load_states_history() == [])

        pytest.raises(KeyError, storage.task_status, task1.id)

        storage.record_task(task1)
        assert(task1.version == 1)
        assert(task1.completed_at is None)
        assert(task1.deleted_at is None)
        assert(storage.load_tasks() == [task1])
        assert(storage.load_recurrence_rules() == [])
        history = storage.load_states_history()
        assert(len(history) == 1)
        assert(history[0].task_id == task1.id)
        assert(history[0].next_state == TaskStatus.pending)

        assert(storage.task_status(task1.id) == TaskStatus.pending)

    def test_task_status(self) -> None:
        storage = InMemoryStorage()
        task1 = Task(title='foo')
        assert(len(storage.load_states_history()) == 0)

        pytest.raises(KeyError, storage.task_status, 'invalid-id')

        storage.record_task(task1)
        assert(len(storage.load_states_history()) == 1)
        assert(task1.version == 1)
        assert(storage.task_status(task1.id) == TaskStatus.pending)

        storage.set_task_status(task1.id, TaskStatus.in_progress)
        assert(len(storage.load_states_history()) == 2)
        assert(storage.task_status(task1.id) == TaskStatus.in_progress)
        assert(exact_one_task(storage.load_tasks(), task1.id).version == 2)

        storage.set_task_status(task1.id, TaskStatus.done)
        assert(len(storage.load_states_history()) == 3)
        assert(storage.task_status(task1.id) == TaskStatus.done)
        assert(exact_one_task(storage.load_tasks(), task1.id).completed_at is not None)
        assert(exact_one_task(storage.load_tasks(), task1.id).deleted_at is None)
        assert(exact_one_task(storage.load_tasks(), task1.id).version == 3)

        storage.set_task_status(task1.id, TaskStatus.cancelled)
        assert(len(storage.load_states_history()) == 4)
        assert(storage.task_status(task1.id) == TaskStatus.cancelled)
        assert(exact_one_task(storage.load_tasks(), task1.id).completed_at is None)
        assert(exact_one_task(storage.load_tasks(), task1.id).deleted_at is None)
        assert(exact_one_task(storage.load_tasks(), task1.id).version == 4)

        storage.set_task_status(task1.id, TaskStatus.pending)
        assert(len(storage.load_states_history()) == 5)
        assert(storage.task_status(task1.id) == TaskStatus.pending)
        assert(exact_one_task(storage.load_tasks(), task1.id).completed_at is None)
        assert(exact_one_task(storage.load_tasks(), task1.id).deleted_at is None)
        assert(exact_one_task(storage.load_tasks(), task1.id).version == 5)

        storage.set_task_status(task1.id, TaskStatus.done)
        assert(len(storage.load_states_history()) == 6)
        assert(storage.task_status(task1.id) == TaskStatus.done)
        assert(exact_one_task(storage.load_tasks(), task1.id).completed_at is not None)
        assert(exact_one_task(storage.load_tasks(), task1.id).deleted_at is None)
        assert(exact_one_task(storage.load_tasks(), task1.id).version == 6)

        storage.set_task_status(task1.id, TaskStatus.deleted)
        assert(len(storage.load_states_history()) == 7)
        assert(storage.task_status(task1.id) == TaskStatus.deleted)
        assert(exact_one_task(storage.load_tasks(), task1.id).completed_at is not None)
        assert(exact_one_task(storage.load_tasks(), task1.id).deleted_at is not None)
        assert(exact_one_task(storage.load_tasks(), task1.id).version == 7)

        pytest.raises(ValueError, storage.set_task_status, task1.id, TaskStatus.pending)

    def test_task_recurrence(self) -> None:
        storage = InMemoryStorage()
        task1 = Task(title='foo')
        task2 = Task(title='bar')

        faked_creation_time = datetime.datetime.fromtimestamp(  # 14th of Novermber 2023
            1700000000, tz=datetime.timezone.utc
        )
        task1.created_at = faked_creation_time
        task1.updated_at = faked_creation_time
        task2.created_at = faked_creation_time
        task2.updated_at = faked_creation_time

        storage.record_task(task1)
        storage.record_task(task2)

        assert(storage.load_recurrence_rules() == [])
        rule1 = RecurrenceRule(
            schedule_type=RecurrenceScheduleType.rrule,
            schedule_expression="FREQ=DAILY"
        )
        storage.set_task_recurrence(task1.id, rule1)

        rule2 = RecurrenceRule(
            schedule_type=RecurrenceScheduleType.cron,
            schedule_expression="0 * * * *"
        )
        storage.set_task_recurrence(task2.id, rule2)

        assert(storage.load_recurrence_rules() == [rule1, rule2])
        assert(exact_one_task(storage.load_tasks(), task1.id).recurrence_rule_id == rule1.id)

        storage.reinitialize_recurrency_states()

        storage.set_task_recurrence(task1.id)
        assert(storage.load_recurrence_rules() == [rule1, rule2])  # there is no auto-clean
        assert(task1.recurrence_rule_id is None)
