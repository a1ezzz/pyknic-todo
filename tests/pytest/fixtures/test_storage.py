
import contextlib
import copy
import threading
import typing
import uuid

from pyknic.lib.uri import URI

from pyknic_todo.models import Task, RecurrenceRule, StateUpdatedEvent, ToDoStorageSettings, Project

from pyknic_todo.storage.plain import PlainTaskStorageProto
from pyknic_todo.storage.plain import PlainRecurrenceRuleStorageProto, PlainStateHistoryStorageProto
from pyknic_todo.storage.plain import PlainStorageProto, PlainSettingsStorageProto, PlainProjectStorageProto
from pyknic_todo.version import __version__


class InMemoryTaskStorage(PlainTaskStorageProto):

    def __init__(self) -> None:
        PlainTaskStorageProto.__init__(self)
        self.__storage: typing.List[Task] = []

    def load_tasks(self) -> typing.List[Task]:
        return copy.deepcopy(self.__storage)

    def record_task(self, task: Task) -> None:
        self.__storage.append(task.model_copy(deep=True))


class InMemoryProjectStorage(PlainProjectStorageProto):

    def __init__(self) -> None:
        PlainProjectStorageProto.__init__(self)
        self.__storage: typing.List[Project] = []

    def load_projects(self) -> typing.List[Project]:
        return copy.deepcopy(self.__storage)

    def record_project(self, project: Project) -> None:
        self.__storage.append(project.model_copy(deep=True))


class InMemoryRuleStorage(PlainRecurrenceRuleStorageProto):

    def __init__(self) -> None:
        PlainRecurrenceRuleStorageProto.__init__(self)
        self.__storage: typing.List[RecurrenceRule] = []

    def load_recurrence_rules(self) -> typing.List[RecurrenceRule]:
        return copy.deepcopy(self.__storage)

    def record_recurrence_rule(self, rule: RecurrenceRule) -> None:
        self.__storage.append(rule.model_copy(deep=True))


class InMemoryHistoryStorage(PlainStateHistoryStorageProto):

    def __init__(self) -> None:
        PlainStateHistoryStorageProto.__init__(self)
        self.__storage: typing.List[StateUpdatedEvent] = []

    def load_states_history(self) -> typing.List[StateUpdatedEvent]:
        return copy.deepcopy(self.__storage)

    def record_history_event(self, event: StateUpdatedEvent) -> None:
        self.__storage.append(event.model_copy(deep=True))


class InMemorySettingsStorage(PlainSettingsStorageProto):

    def __int__(self) -> None:
        PlainSettingsStorageProto.__init__(self)
        self.__settings = ToDoStorageSettings(comment='InMemory storage', scheme_version=__version__)

    def storage_id(self) -> uuid.UUID:
        return self.__settings.id


class InMemoryStorage(PlainStorageProto):

    def __init__(self) -> None:
        PlainStorageProto.__init__(self)
        self.__lock = threading.Lock()

        self.__ts = InMemoryTaskStorage()
        self.__ps = InMemoryProjectStorage()
        self.__rs = InMemoryRuleStorage()
        self.__hs = InMemoryHistoryStorage()
        self.__se = InMemorySettingsStorage()

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

    def _settings(self) -> PlainSettingsStorageProto:
        return self.__se

    def _project(self) -> PlainProjectStorageProto:
        return self.__ps

    def purge_data(
        self, remove_deleted_task: bool, remove_completed_task: bool, reduce_history: bool, remove_empty_projects: bool
    ) -> int:
        raise NotImplementedError('This is not a real implementation')

    @classmethod
    def create_storage(cls, storage_uri: URI) -> 'PlainStorageProto':
        return cls()

    @classmethod
    def update_scheme(cls, scheme_uri: URI) -> str:
        raise NotImplementedError('This is not a real implementation')

    @classmethod
    def latest_migration(cls) -> str:
        raise NotImplementedError('This is not a real implementation')
