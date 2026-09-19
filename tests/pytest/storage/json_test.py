
import pathlib
import tempfile
import typing
import uuid

import pytest

from pyknic.lib.uri import URI

from pyknic_todo.models import Task, TaskPriority, RecurrenceRule, RecurrenceScheduleType, RecurrenceEndCondtionType
from pyknic_todo.models import EndCondition, TaskStatus, StateHistoryEvent

from pyknic_todo.storage.plain import PlainTaskStorageProto, PlainRecurrenceRuleStorageProto
from pyknic_todo.storage.plain import PlainStateHistoryStorageProto, PlainStorageProto

from pyknic_todo.storage.json import StorageLock, JsonTaskStorage, JsonRecurrenceRuleStorage, JsonHistoryStorage
from pyknic_todo.storage.json import JsonStorage, JsonFile, __json_storage_scheme__


@pytest.fixture
def json_tmp_uri() -> typing.Generator[URI, None, None]:

    with tempfile.TemporaryDirectory(prefix='pytest-pyknic_todo', suffix='json_tmp_uri_fixture') as tmp_dir:
        yield URI.parse(f'{__json_storage_scheme__}:///{tmp_dir}')


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

        ts.append_task(task1)
        assert(task1.storage_origin == storage_id)
        assert(task2.storage_origin is None)

        ts.append_task(task2)
        assert(task1.storage_origin == storage_id)
        assert(task2.storage_origin == storage_id)

        tasks = ts.load_tasks()
        assert(len(tasks) == 2)
        assert(tasks[0].title == "Isolated task #1")
        assert(tasks[0].tags == ["iso"])
        assert(tasks[1].title == "Isolated task #2")
        assert(tasks[1].priority == TaskPriority("low"))

        ts.save_tasks([task2])
        tasks = ts.load_tasks()
        assert(len(tasks) == 1)
        assert(tasks[0].title == "Isolated task #2")
        assert(tasks[0].priority == TaskPriority("low"))

    def test_context(self, tmp_path: pathlib.Path) -> None:
        ts = JsonTaskStorage(uuid.uuid4(), tmp_path, lock=StorageLock(lock_file=(tmp_path / '.lock')))

        task = Task(
            title="Isolated task",
            description="Details",
            priority=TaskPriority("high"),
            tags=["iso"],
        )
        ts.append_task(task)

        tasks = ts.load_tasks()
        assert(len(tasks) == 1)
        assert(tasks[0].title == "Isolated task")
        assert(tasks[0].priority == TaskPriority("high"))
        assert(tasks[0].tags == ["iso"])

        with ts.updater_context(str(task.id)[:8], query_full_match=False) as tc:
            tc_task = tc()
            assert(tc_task.title == "Isolated task")
            assert(tc_task.priority == TaskPriority("high"))
            assert(tc_task.tags == ["iso"])

            tc_task.title = 'Updated task'
            tc.commit()
            tc_task.tags = ["foo"]
            tc.commit()

            tc_task.priority == TaskPriority("low")  # there is no commit, so change isn't saved

        tasks = ts.load_tasks()
        assert(len(tasks) == 1)
        assert(tasks[0].title == "Updated task")
        assert(tasks[0].priority == TaskPriority("high"))
        assert(tasks[0].tags == ["foo"])

    def test_multiline(self, tmp_path: pathlib.Path) -> None:
        ts = JsonTaskStorage(uuid.uuid4(), tmp_path, lock=StorageLock(lock_file=(tmp_path / '.lock')))

        task_description = """The GNU General Public License is a free, copyleft license for...

        The licenses for most software and other practical works are designed to take away your..."""

        ts.append_task(Task(title="Isolated task", description=task_description))
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
            end_condition=EndCondition(
                condition_type=RecurrenceEndCondtionType.count,
                max_occurrences=5
            )
        )

        rs.append_recurrence_rule(rule1)
        rs.append_recurrence_rule(rule2)

        rules = rs.load_recurrence_rules()
        assert(len(rules) == 2)
        assert(rules[0].schedule_type == RecurrenceScheduleType.cron)
        assert(rules[1].schedule_type == RecurrenceScheduleType.rrule)

        rs.save_recurrence_rules([rule2])
        rules = rs.load_recurrence_rules()
        assert(len(rules) == 1)
        assert(rules[0].schedule_type == RecurrenceScheduleType.rrule)


class TestJsonHistoryStorage:

    def test(self, tmp_path: pathlib.Path) -> None:
        storage_id = uuid.uuid4()

        hs = JsonHistoryStorage(storage_id, tmp_path, lock=StorageLock(lock_file=(tmp_path / '.lock')))
        assert(isinstance(hs, PlainStateHistoryStorageProto))

        assert((tmp_path / JsonFile.tasks.value).exists() is False)
        assert((tmp_path / JsonFile.recurrence_rules.value).exists() is False)
        assert((tmp_path / JsonFile.states_history.value).exists() is True)

        task_id = uuid.uuid4()  # there is no check for a task existance

        state1 = StateHistoryEvent(
            task_id=task_id,
            next_state=TaskStatus.in_progress
        )

        state2 = StateHistoryEvent(
            task_id=task_id,
            next_state=TaskStatus.done
        )

        assert(state1.storage_origin is None)
        assert(state2.storage_origin is None)

        hs.record_history_event(state1)
        assert(state1.storage_origin == storage_id)
        assert(state2.storage_origin is None)
        assert(hs.load_history() == [state1])
        assert(hs.task_latest_status(task_id) == TaskStatus.in_progress)

        hs.record_history_event(state2)
        assert(state1.storage_origin == storage_id)
        assert(state2.storage_origin == storage_id)
        assert(hs.load_history() == [state1, state2])
        assert(hs.task_latest_status(task_id) == TaskStatus.done)

    def test_multiline(self, tmp_path: pathlib.Path) -> None:
        hs = JsonHistoryStorage(uuid.uuid4(), tmp_path, lock=StorageLock(lock_file=(tmp_path / '.lock')))

        task_id = uuid.uuid4()  # there is no check for a task existance

        state_comment = """The GNU General Public License is a free, copyleft license for...

        The licenses for most software and other practical works are designed to take away your..."""

        state1 = StateHistoryEvent(
            task_id=task_id,
            next_state=TaskStatus.in_progress,
            comment=state_comment
        )

        hs.record_history_event(state1)
        assert(hs.load_history() == [state1])
        assert(hs.task_latest_status(str(task_id)[:8]) == TaskStatus.in_progress)

        history = hs.find_events_for_task(str(task_id)[:8])
        assert(len(history) == 1)
        assert(history[0].comment == state_comment)


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
        s.append_task(task)
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
