
import contextlib
import threading
import typing
import uuid

from pyknic_todo.models import Task, RecurrenceRule, StateHistoryEvent

from pyknic_todo.storage.plain import TaskStorageUpdaterContextProto, PlainTaskStorageProto
from pyknic_todo.storage.plain import PlainRecurrenceRuleStorageProto, PlainStateHistoryStorageProto
from pyknic_todo.storage.plain import PlainStorageProto

from pyknic_todo.storage.helpers import exact_one_task


class InMemoryTaskContext(TaskStorageUpdaterContextProto):

    def __init__(self, task_storage: PlainTaskStorageProto, task: Task):
        TaskStorageUpdaterContextProto.__init__(self)
        self.__ts = task_storage
        self.__task = task

    def __call__(self) -> Task:
        return self.__task

    def commit(self) -> None:
        def patch_tasks() -> typing.Generator[Task, None, None]:

            task_patched = False

            for i in self.__ts.load_tasks():
                if i.id != self.__task.id:
                    yield i
                elif not task_patched:
                    task_patched = True
                    yield self.__task
                else:
                    raise ValueError('!')

            if not task_patched:
                raise ValueError('!')

        self.__ts.save_tasks(list(patch_tasks()))


class InMemoryTaskStorage(PlainTaskStorageProto):

    def __init__(self) -> None:
        PlainTaskStorageProto.__init__(self)
        self.__storage: typing.List[Task] = []

    def load_tasks(self) -> typing.List[Task]:
        return self.__storage.copy()

    def save_tasks(self, tasks: typing.List[Task]) -> None:
        self.__storage = tasks.copy()

    def append_task(self, task: Task) -> None:
        self.__storage.append(task)

    def updater_context(
        self, task_id_query: typing.Union[uuid.UUID, str], query_full_match: bool = True
    ) -> TaskStorageUpdaterContextProto:

        return InMemoryTaskContext(
            self, exact_one_task(self.load_tasks(), task_id_query, query_full_match=query_full_match)
        )


class InMemoryRuleStorage(PlainRecurrenceRuleStorageProto):

    def __init__(self) -> None:
        PlainRecurrenceRuleStorageProto.__init__(self)
        self.__storage: typing.List[RecurrenceRule] = []

    def load_recurrence_rules(self) -> typing.List[RecurrenceRule]:
        return self.__storage.copy()

    def save_recurrence_rules(self, rules: typing.List[RecurrenceRule]) -> None:
        self.__storage = rules.copy()

    def append_recurrence_rule(self, rule: RecurrenceRule) -> None:
        self.__storage.append(rule)


class InMemoryHistoryStorage(PlainStateHistoryStorageProto):

    def __init__(self) -> None:
        PlainStateHistoryStorageProto.__init__(self)
        self.__storage: typing.List[StateHistoryEvent] = []

    def load_history(self) -> typing.List[StateHistoryEvent]:
        return self.__storage.copy()

    def record_history_event(self, event: StateHistoryEvent) -> None:
        self.__storage.append(event)


class InMemoryStorage(PlainStorageProto):

    def __init__(self) -> None:
        PlainStorageProto.__init__(self)
        self.__lock = threading.Lock()

        self.__ts = InMemoryTaskStorage()
        self.__rs = InMemoryRuleStorage()
        self.__hs = InMemoryHistoryStorage()

    @contextlib.contextmanager
    def lock(self, exclusive: bool = True, blocking: bool = True) -> typing.Generator[None, None, None]:
        assert(exclusive)  # this in-memory storage doesn't support shared lock

        lock_acuired = self.__lock.acquire(blocking=blocking)
        if not lock_acuired:
            raise OSError('In-memory storage is not locked')
        yield
        self.__lock.release()

    def _tasks(self) -> PlainTaskStorageProto:
        return self.__ts

    def _recurrence_rules(self) -> PlainRecurrenceRuleStorageProto:
        return self.__rs

    def _history(self) -> PlainStateHistoryStorageProto:
        return self.__hs
