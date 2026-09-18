# -*- coding: utf-8 -*-
# pyknic_todo/storage/json.py
#
# Copyright (C) 2026 the pyknic_todo authors and contributors
# <see AUTHORS file>
#
# This file is part of pyknic_todo.
#
# pyknic_todo is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pyknic_todo is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with pyknic_todo.  If not, see <http://www.gnu.org/licenses/>.


import contextlib
import enum
import fcntl
import os
import pathlib
import threading
import typing
import uuid

import pydantic

from pyknic_todo.models import RecurrenceRule, StateHistoryEvent, Task, TaskStatus
from pyknic_todo.settings import Settings

from .helpers import exact_one_task, partial_uuid_select

from .plain import TaskStorageUpdaterContextProto, PlainTaskStorageProto, PlainStateHistoryStorageProto
from .plain import PlainRecurrenceRuleStorageProto, PlainStorageProto


@enum.unique
class JsonFile(enum.Enum):
    """Possible files that this storage creates."""

    tasks = "tasks.json"                        # file that stores :class:`.Task` objects
    recurrence_rules = "recurrence_rules.json"  # file that stores :class:`.RecurrenceRule` objects
    states_history = "states_history.json"      # file that stores :class:`.StateHistoryEvent` objects
    # TODO: add settings with client_id!


@enum.unique
class JsonFileModels(enum.Enum):
    """Models that are stored in files."""
    tasks = Task
    recurrence_rules = RecurrenceRule
    states_history = StateHistoryEvent


class StorageLock:
    """Handles file-level and thread-level locking across storage operations."""

    def __init__(self, lock_file: pathlib.Path) -> None:
        """Create a new lock.

        :param lock_file: a path where a lock-file must be created (parent directory will be created automatically)
        """

        self.__lock_file = lock_file.resolve()
        self.__thread_lock = threading.Lock()

    @contextlib.contextmanager
    def lock(self, blocking: bool = True) -> typing.Iterator[None]:
        """Try to lock a file

        :param blocking: wheter to wait for a lock indefinitely long or try once and raise exception if a lock wasn't
        acquired
        """

        # TODO: think of timeout for blocking mode! Even for self.__thread_lock!

        fd = None
        flock_succeded = False

        try:

            with self.__thread_lock:
                lock_file_dir = self.__lock_file.parent
                lock_file_dir.mkdir(parents=True, exist_ok=True)

                op = fcntl.LOCK_EX
                if not blocking:
                    op |= fcntl.LOCK_NB

                fd = os.open(self.__lock_file, os.O_CREAT | os.O_RDWR, 0o666)
                fcntl.flock(fd, op)
                flock_succeded = True

            yield

        finally:

            with self.__thread_lock:
                if flock_succeded:
                    assert(fd is not None)
                    fcntl.flock(fd, fcntl.LOCK_UN)
                if fd is not None:
                    os.close(fd)


class _BaseJsonEntityStorage:
    """Base storage handling JSON file persistence and synchronization for an entity."""

    def __init__(self, file_type: JsonFile, lock: StorageLock, settings: Settings) -> None:
        """Create a new basic storage and initialize an empty file if there wasn't before

        :param file_type: a type of a file this storage is used for
        :param lock: exclusive I/O lock
        :param settings: storage settings
        """

        self.__file_type = file_type
        self.__model_cls = getattr(JsonFileModels, self.__file_type.name).value
        self.__file_path = settings.data_dir / str(self.__file_type.value)

        self.__lock_manager = lock
        self.__ensure_file()

    def _read_json[T](self) -> typing.List[T]:
        """ Read, parse and return list of inner objects"""

        with self.__lock_manager.lock():
            with open(self.__file_path, "r", encoding="utf-8") as f:

                result = []
                line = f.readline()

                while line:
                    stripped_line = line.strip()
                    if stripped_line:
                        result.append(self.__model_cls.model_validate_json(stripped_line))
                    line = f.readline()

                return result

    def __serialize(self, obj: pydantic.BaseModel) -> str:
        """Return a one-line JSON-string that represent a specified object

        :param obj: object to serialize
        """
        # TODO: test multiline comment!
        #  there are comments in tasks and states (elsewhere?)

        model_dump = obj.model_dump_json()
        if '\n' in model_dump:
            raise RuntimeError('Invalid model serialization! Serialization logic must be changed!')
        return model_dump

    def _write_json(self, data: typing.Sequence[pydantic.BaseModel]) -> None:
        """Replace a file with a new set of inner objects.

        :param data: a new set of complete data to save
        """
        # TODO: check that there is no duplicates (entries with the same id)

        with self.__lock_manager.lock():
            with open(self.__file_path, "w", encoding="utf-8") as f:
                for d in data:
                    f.write(self.__serialize(d))
                    f.write("\n")

    def _append_json(self, data: pydantic.BaseModel) -> None:
        """Append a new object to a current set
        """
        # TODO: check that there is no duplicates (entries with the same id)

        with self.__lock_manager.lock():
            with open(self.__file_path, "a", encoding="utf-8") as f:
                f.write(self.__serialize(data))
                f.write("\n")

    def __ensure_file(self) -> None:
        """Check if there is a file and create an empty one if the file doesn't exist
        """

        with self.__lock_manager.lock():
            self.__file_path.parent.mkdir(parents=True, exist_ok=True)

            if not self.__file_path.exists():
                with open(self.__file_path, "a", encoding="utf-8") as f:
                    f.write('')


class JsonTaskStorage(PlainTaskStorageProto, _BaseJsonEntityStorage):
    """Storage that saves :class:`.Task` objects"""

    class UpdaterContext(TaskStorageUpdaterContextProto):
        """The :class:`.TaskStorageUpdaterContextProto` implementation for the :class:`.JsonTaskStorage` class
        """

        def __init__(
            self,
            storage: PlainTaskStorageProto,
            task_id_query: typing.Union[uuid.UUID, str],
            query_full_match: bool = True
        ):
            """Create a new context manager

            :param storage: original tasks storage
            :param task_id_query: a task identifier (a partial uuid submittion is supported when
            the "query_full_match" argument is False)
            :param query_full_match: whether the "task_id_query" argument is a complete id or a partial one
            """

            TaskStorageUpdaterContextProto.__init__(self)
            self.__storage = storage
            self.__all_tasks = self.__storage.load_tasks()
            self.__task = exact_one_task(self.__all_tasks, task_id_query, query_full_match=query_full_match)

        def __call__(self) -> Task:
            """:meth:`.TaskStorageUpdaterContextProto.__call__` implementation
            """
            return self.__task

        def commit(self) -> None:
            """:meth:`.TaskStorageUpdaterContextProto.commit` implementation
            """
            self.__storage.save_tasks(self.__all_tasks)

    def __init__(
        self,
        lock: StorageLock,
        settings: Settings
    ) -> None:
        """ Create a new task storage

        :param lock: exclusive I/O lock
        :param settings: storage settings
        """

        PlainTaskStorageProto.__init__(self)
        _BaseJsonEntityStorage.__init__(
            self,
            file_type=JsonFile.tasks,
            lock=lock,
            settings=settings
        )

    def load_tasks(self) -> typing.List[Task]:
        """ :meth:`.PlainTaskStorageProto.load_tasks` method implementation
        """
        return self._read_json()

    def save_tasks(self, tasks: typing.Sequence[Task]) -> None:
        """ :meth:`.PlainTaskStorageProto.save_tasks` method implementation
        """
        self._write_json(tasks)

    def updater_context(
        self,
        id_query: typing.Union[uuid.UUID, str],
        query_full_match: bool = True
    ) -> TaskStorageUpdaterContextProto:
        """ :meth:`.PlainTaskStorageProto.updater_context` method implementation
        """
        return JsonTaskStorage.UpdaterContext(self, id_query, query_full_match=query_full_match)

    def append_task(self, task: Task) -> None:
        """ :meth:`.PlainTaskStorageProto.append_task` method implementation
        """
        self._append_json(task)


class JsonRecurrenceRuleStorage(PlainRecurrenceRuleStorageProto, _BaseJsonEntityStorage):
    """Storage that saves :class:`.RecurrenceRule` objects"""

    def __init__(
        self,
        lock: StorageLock,
        settings: Settings
    ) -> None:
        """ Create a new rule storage

        :param lock: exclusive I/O lock
        :param settings: storage settings
        """

        PlainRecurrenceRuleStorageProto.__init__(self)
        _BaseJsonEntityStorage.__init__(
            self,
            file_type=JsonFile.recurrence_rules,
            lock=lock,
            settings=settings,
        )

    def load_recurrence_rules(self) -> typing.List[RecurrenceRule]:
        """ :meth:`.PlainTaskStorageProto.load_recurrence_rules` method implementation
        """
        return self._read_json()

    def save_recurrence_rules(self, rules: typing.List[RecurrenceRule]) -> None:
        """ :meth:`.PlainTaskStorageProto.save_recurrence_rules` method implementation
        """
        self._write_json(rules)

    def append_recurrence_rule(self, rule: RecurrenceRule) -> None:
        """ :meth:`.PlainTaskStorageProto.append_recurrence_rule` method implementation
        """
        self._append_json(rule)


class JsonHistoryStorage(PlainStateHistoryStorageProto, _BaseJsonEntityStorage):
    """Storage that saves :class:`.StateHistoryEvent` objects"""

    def __init__(
        self,
        lock: StorageLock,
        settings: Settings
    ) -> None:
        """ Create a new state-history storage

        :param lock: exclusive I/O lock
        :param settings: storage settings
        """

        PlainStateHistoryStorageProto.__init__(self)
        _BaseJsonEntityStorage.__init__(
            self,
            file_type=JsonFile.states_history,
            lock=lock,
            settings=settings,
        )

    def load_history(self) -> typing.List[StateHistoryEvent]:
        """ :meth:`.PlainStateHistoryStorageProto.load_history` method implementation
        """
        return self._read_json()

    def find_events_for_task(self, task_id_query: typing.Union[uuid.UUID, str]) -> typing.List[StateHistoryEvent]:
        """ :meth:`.PlainStateHistoryStorageProto.find_events_for_task` method implementation
        """
        return [e for e in self.load_history() if partial_uuid_select(e.task_id, task_id_query)]

    def task_latest_status(self, task_id_query: typing.Union[uuid.UUID, str]) -> TaskStatus:
        """ :meth:`.PlainStateHistoryStorageProto.task_latest_status` method implementation
        """
        events = self.find_events_for_task(task_id_query)
        if events:
            return (events[-1].next_state)

        raise ValueError(f'Task id "{task_id_query}" was not found')

    def record_history_event(self, event: StateHistoryEvent) -> None:
        """ :meth:`.PlainStateHistoryStorageProto.record_history_event` method implementation
        """
        self._append_json(event)


class JsonStorage(PlainStorageProto):
    """JSON facade storage coordinating JsonTaskStorage, JsonRecurrenceRuleStorage, and JsonHistoryStorage."""

    def __init__(self, settings: Settings) -> None:
        """ Create a new storage

        :param settings: storage settings
        """
        PlainStorageProto.__init__(self)
        self.settings = settings

        self.data_dir = self.settings.data_dir.resolve()
        self.__lock = StorageLock(lock_file=(self.data_dir / ".lock"))

        self.__ts = JsonTaskStorage(settings=self.settings, lock=self.__lock)
        self.__rs = JsonRecurrenceRuleStorage(settings=self.settings, lock=self.__lock)
        self.__hs = JsonHistoryStorage(settings=self.settings, lock=self.__lock)

    def _tasks(self) -> JsonTaskStorage:
        """ :meth:`.PlainStorageProto._tasks` method implementation
        """
        return self.__ts

    def _recurrence_rules(self) -> JsonRecurrenceRuleStorage:
        """ :meth:`.PlainStorageProto._recurrence_rules` method implementation
        """
        return self.__rs

    def _history(self) -> JsonHistoryStorage:
        """ :meth:`.PlainStorageProto._history` method implementation
        """
        return self.__hs
