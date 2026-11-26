
import datetime
import pathlib
import multiprocessing
import uuid

import pytest

from pyknic.lib.uri import URI

from pyknic_todo.models import Task, TaskPriority, RecurrenceRule, RecurrenceScheduleType, TaskStatus
from pyknic_todo.models import StateUpdatedEvent

from pyknic_todo.storage.plain import PlainTaskStorageProto, PlainRecurrenceRuleStorageProto
from pyknic_todo.storage.plain import PlainStateHistoryStorageProto, PlainStorageProto

from pyknic_todo.storage.json.implementation import StorageLock, JsonTaskStorage, JsonRecurrenceRuleStorage
from pyknic_todo.storage.json.implementation import JsonHistoryStorage, JsonStorage, JsonSettingsStorage
from pyknic_todo.storage.json.implementation import __json_storage_scheme__
from pyknic_todo.storage.json.enums import JsonFile


def _concurrent_create_worker(storage_uri: URI, index: int) -> None:
    storage = JsonStorage(storage_uri)
    storage.record_task(Task(title=f"Concurrent task {index}"))


class TestStorageLock:

    def test(self, tmp_path: pathlib.Path) -> None:
        lock1 = StorageLock(tmp_path / '.lock')
        lock2 = StorageLock(tmp_path / '.lock')
        lock3 = StorageLock(tmp_path / '.lock3')

        with lock1.lock():

            with pytest.raises(BlockingIOError):
                with lock2.lock(blocking=False):
                    pass

            with lock3.lock():
                assert(1)

            with lock3.lock(blocking=False):
                assert(1)


class TestJsonTaskStorage:

    def test(self, tmp_path: pathlib.Path) -> None:
        storage_id = uuid.uuid4()
        ts = JsonTaskStorage(storage_id, tmp_path, lock=StorageLock(lock_file=(tmp_path / '.lock')))
        assert(isinstance(ts, PlainTaskStorageProto))

        assert((tmp_path / JsonFile.tasks.value).exists() is True)
        assert((tmp_path / JsonFile.recurrence_rules.value).exists() is False)
        assert((tmp_path / JsonFile.states_history.value).exists() is False)

        task1 = Task(
            title="Isolated task #1",
            description="Details",
            priority=TaskPriority("high"),
            tags=["iso"],
        )
        task2 = Task(
            title="Isolated task #2",
            description="Details",
            priority=TaskPriority("low"),
        )

        assert(task1.storage_origin is None)
        assert(task2.storage_origin is None)

        ts.record_task(task1)
        assert(task1.storage_origin == storage_id)
        assert(task2.storage_origin is None)

        ts.record_task(task2)
        assert(task1.storage_origin == storage_id)
        assert(task2.storage_origin == storage_id)

        tasks = ts.load_tasks()
        assert(len(tasks) == 2)
        assert(tasks[0].title == "Isolated task #1")
        assert(tasks[0].tags == ["iso"])
        assert(tasks[1].title == "Isolated task #2")
        assert(tasks[1].priority == TaskPriority("low"))

        task2.title = "New Isolated task #2"
        task2.description = "More details"
        task2.priority = TaskPriority("high")
        task2.version += 1
        ts.record_task(task2)

        tasks = ts.load_tasks()
        assert(len(tasks) == 3)
        assert(tasks[0].id == task1.id)
        assert(tasks[0].title == "Isolated task #1")
        assert(tasks[0].tags == ["iso"])
        assert(tasks[1].id == task2.id)
        assert(tasks[1].title == "Isolated task #2")
        assert(tasks[1].priority == TaskPriority("low"))
        assert(tasks[2].id == task2.id)
        assert(tasks[2].title == "New Isolated task #2")
        assert(tasks[2].priority == TaskPriority("high"))

    def test_multiline(self, tmp_path: pathlib.Path) -> None:
        ts = JsonTaskStorage(uuid.uuid4(), tmp_path, lock=StorageLock(lock_file=(tmp_path / '.lock')))

        task_description = """The GNU General Public License is a free, copyleft license for...

        The licenses for most software and other practical works are designed to take away your..."""

        ts.record_task(Task(title="Isolated task", description=task_description))
        assert(ts.load_tasks()[0].description == task_description)


class TestJsonRecurrenceRuleStorage:

    def test(self, tmp_path: pathlib.Path) -> None:
        rs = JsonRecurrenceRuleStorage(tmp_path, lock=StorageLock(lock_file=(tmp_path / '.lock')))
        assert(isinstance(rs, PlainRecurrenceRuleStorageProto))

        assert((tmp_path / JsonFile.tasks.value).exists() is False)
        assert((tmp_path / JsonFile.recurrence_rules.value).exists() is True)
        assert((tmp_path / JsonFile.states_history.value).exists() is False)

        rule1 = RecurrenceRule(
            schedule_type=RecurrenceScheduleType.cron,
            schedule_expression="0 9 * * 1"
        )

        rule2 = RecurrenceRule(
            schedule_type=RecurrenceScheduleType.rrule,
            schedule_expression="FREQ=DAILY",
            until_date='2025-05-25T05:25:25Z'  # type: ignore[arg-type]  # this is ok, this is a test!
        )

        rs.record_recurrence_rule(rule1)
        rs.record_recurrence_rule(rule2)

        rules = rs.load_recurrence_rules()
        assert(len(rules) == 2)
        assert(rules[0].schedule_type == RecurrenceScheduleType.cron)
        assert(rules[1].schedule_type == RecurrenceScheduleType.rrule)


class TestJsonHistoryStorage:

    def test(self, tmp_path: pathlib.Path) -> None:
        storage_id = uuid.uuid4()

        hs = JsonHistoryStorage(storage_id, tmp_path, lock=StorageLock(lock_file=(tmp_path / '.lock')))
        assert(isinstance(hs, PlainStateHistoryStorageProto))

        assert((tmp_path / JsonFile.tasks.value).exists() is False)
        assert((tmp_path / JsonFile.recurrence_rules.value).exists() is False)
        assert((tmp_path / JsonFile.states_history.value).exists() is True)

        task_id = uuid.uuid4()  # there is no check for a task existance

        state1 = StateUpdatedEvent(
            task_id=task_id,
            next_state=TaskStatus.in_progress
        )

        state2 = StateUpdatedEvent(
            task_id=task_id,
            next_state=TaskStatus.done
        )

        assert(state1.storage_origin is None)
        assert(state2.storage_origin is None)

        hs.record_history_event(state1)
        assert(state1.storage_origin == storage_id)
        assert(state2.storage_origin is None)
        assert(hs.load_states_history() == [state1])

        hs.record_history_event(state2)
        assert(state1.storage_origin == storage_id)
        assert(state2.storage_origin == storage_id)
        assert(hs.load_states_history() == [state1, state2])

    def test_multiline(self, tmp_path: pathlib.Path) -> None:
        hs = JsonHistoryStorage(uuid.uuid4(), tmp_path, lock=StorageLock(lock_file=(tmp_path / '.lock')))

        task_id = uuid.uuid4()  # there is no check for a task existance

        state_comment = """The GNU General Public License is a free, copyleft license for...

        The licenses for most software and other practical works are designed to take away your..."""

        state1 = StateUpdatedEvent(
            task_id=task_id,
            next_state=TaskStatus.in_progress,
            comment=state_comment
        )

        hs.record_history_event(state1)
        assert(hs.load_states_history() == [state1])

        history = hs.find_events_for_task(str(task_id)[:8])
        assert(len(history) == 1)
        assert(history[0].comment == state_comment)


class TestJsonSettingsStorage:

    def test(self, tmp_path: pathlib.Path) -> None:
        storage = JsonSettingsStorage(
            tmp_path, JsonStorage.latest_migration(), lock=StorageLock(lock_file=(tmp_path / '.lock'))
        )

        assert(isinstance(storage, JsonSettingsStorage))

        assert((tmp_path / JsonFile.tasks.value).exists() is False)
        assert((tmp_path / JsonFile.recurrence_rules.value).exists() is False)
        assert((tmp_path / JsonFile.states_history.value).exists() is False)
        assert((tmp_path / JsonFile.settings.value).exists() is True)

        init_id = storage.storage_id()

        storage = JsonSettingsStorage(
            tmp_path, JsonStorage.latest_migration(), lock=StorageLock(lock_file=(tmp_path / '.lock'))
        )
        assert(init_id == storage.storage_id())


class TestJsonStorage:

    def test(self, json_tmp_uri: URI) -> None:
        assert(json_tmp_uri.path)

        s = JsonStorage.create_storage(json_tmp_uri)
        assert(isinstance(s, PlainStorageProto))

        assert(isinstance(s._tasks(), JsonTaskStorage))
        assert(isinstance(s._recurrence_rules(), JsonRecurrenceRuleStorage))
        assert(isinstance(s._history(), JsonHistoryStorage))

        assert((pathlib.Path('/') / pathlib.Path(json_tmp_uri.path) / JsonFile.tasks.value).exists() is True)
        assert((pathlib.Path('/') / pathlib.Path(json_tmp_uri.path) / JsonFile.recurrence_rules.value).exists() is True)
        assert((pathlib.Path('/') / pathlib.Path(json_tmp_uri.path) / JsonFile.states_history.value).exists() is True)

        # smoke test

        task = Task(
            title="Isolated task",
            description="Details",
            priority=TaskPriority("high"),
            tags=["iso"],
        )

        assert(task.storage_origin is None)
        s.record_task(task)
        assert(task.storage_origin == s.storage_id())
        assert(s.set_task_status(task.id, TaskStatus.cancelled))
        assert(s.task_status(str(task.id)[:8]) == TaskStatus.cancelled)

    def test_exception(self, json_tmp_uri: URI) -> None:
        assert(json_tmp_uri.path)

        pytest.raises(ValueError, JsonStorage.create_storage, URI(scheme='invalid-scheme', path=json_tmp_uri.path))
        pytest.raises(ValueError, JsonStorage.create_storage, URI(scheme=__json_storage_scheme__))  # path is not set

        data_path = pathlib.Path('/') / json_tmp_uri.path
        data_path.rmdir()
        data_path.touch()
        pytest.raises(ValueError, JsonStorage.create_storage, json_tmp_uri)  # data directory is a file

        data_path.unlink()
        data_path.mkdir()
        _ = JsonStorage.create_storage(json_tmp_uri)  # this is ok

    def test_concurrency(self, json_tmp_uri: URI) -> None:

        procs = [
            multiprocessing.Process(
                target=_concurrent_create_worker,
                args=(json_tmp_uri, i),
            )
            for i in range(10)
        ]
        for p in procs:
            p.start()
        for p in procs:
            p.join()

        storage = JsonStorage(json_tmp_uri)
        tasks = storage.load_tasks()
        assert(len(tasks) == 10)
        history = storage.load_states_history()
        assert(len(history) == 10)

    @pytest.mark.parametrize(
        "schedule_type, schedule_expr", [
            (RecurrenceScheduleType.cron, '0 12 * * *'),
            (RecurrenceScheduleType.rrule, 'FREQ=DAILY')
        ]
    )
    def test_cron_recurrency(
        self, json_tmp_uri: URI, schedule_type: RecurrenceScheduleType, schedule_expr: str
    ) -> None:
        storage = JsonStorage(json_tmp_uri)

        task = Task(title="Sample task")
        storage.record_task(task)  # this populates some fields like storage_origin
        assert(storage.task_status(task.id) == TaskStatus.pending)
        events = storage.load_states_history()
        assert(len(events) == 1)

        cron_rrule = RecurrenceRule(
            schedule_type=schedule_type,
            schedule_expression=schedule_expr
        )
        storage.set_task_recurrence(task.id, cron_rrule)

        task = storage.load_tasks()[0]  # set_task_recurrence replaces inner object
        assert(task.recurrence_rule_id is not None)
        assert(storage.task_status(task.id) == TaskStatus.pending)  # recurrence rule does not affect state

        faked_creation_time = datetime.datetime.fromtimestamp(  # 14th of Novermber 2023
            1700000000, tz=datetime.timezone.utc
        )
        task.created_at = faked_creation_time
        task.updated_at = faked_creation_time
        event = events[0]
        event.created_at = faked_creation_time
        assert(storage.task_status(task.id) == TaskStatus.pending)  # no affect still

        storage._tasks()._write_json([task])
        storage._history()._write_json([event])

        storage = JsonStorage(json_tmp_uri)  # forces reinitialization
        events = storage.load_states_history()

        assert(len(events) == 3)
        assert(events[1].next_state == TaskStatus.skipped)
        assert(events[2].next_state == TaskStatus.pending)
