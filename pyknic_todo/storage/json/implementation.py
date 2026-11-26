# -*- coding: utf-8 -*-
# pyknic_todo/storage/json/implementation.py
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
import fcntl
import json
import os
import pathlib
import threading
import typing
import uuid

import packaging.version
import pydantic

from pyknic.lib.log import Logger
from pyknic.lib.registry import register_api
from pyknic.lib.uri import URI

from pyknic_todo.models import RecurrenceRule, StateUpdatedEvent, Task, ToDoStorageSettings
from pyknic_todo.version import __version__

from pyknic_todo.storage.helpers import partial_uuid_select

from pyknic_todo.storage.proto import SchemeMigrationRequiredError, SchemeMigrationCallError
from pyknic_todo.storage.plain import PlainTaskStorageProto, PlainStateHistoryStorageProto
from pyknic_todo.storage.plain import PlainRecurrenceRuleStorageProto, PlainStorageProto, PlainSettingsStorageProto

from pyknic_todo.storage.registry import __storage_registry__

from .migrations.registry import __json_migrations_registry__
from .enums import JsonFile, JsonFileModels
from .helpers import read_jsonl_file


class StorageLock:
    """Handles file-level and thread-level locking across storage operations."""

    def __init__(self, lock_file: pathlib.Path) -> None:
        """Create a new lock.

        :param lock_file: a path where a lock-file must be created (parent directory will be created automatically)
        """

        self.__lock_file = lock_file.resolve()
        self.__thread_lock = threading.Lock()

    @contextlib.contextmanager
    def lock(self, blocking: bool = True) -> typing.Generator[None, None, None]:
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
                    if fd is None:
                        RuntimeError('Required file descriptor is not found')

                    fcntl.flock(fd, fcntl.LOCK_UN)  # type: ignore[arg-type]
                if fd is not None:
                    os.close(fd)


_BaseJsonGenVar = typing.TypeVar('_BaseJsonGenVar')


class _BaseJsonEntityStorage:
    """Base storage handling JSON file persistence and synchronization for an entity."""

    def __init__(self, data_dir: pathlib.Path, file_type: JsonFile, lock: StorageLock) -> None:
        """Create a new basic storage and initialize an empty file if there wasn't before

        :param data_dir: absolute path to a directory where a storage file should be created
        :param file_type: a type of a file this storage is used for
        :param lock: exclusive I/O lock
        """

        self.__file_type = file_type
        self.__model_cls = getattr(JsonFileModels, self.__file_type.name).value
        self.__file_path = data_dir / str(self.__file_type.value)

        self.__lock_manager = lock
        self._ensure_file()

    def _read_json(self) -> typing.List[_BaseJsonGenVar]:
        """ Read, parse and return list of inner objects"""

        with self.__lock_manager.lock():
            result = []
            for line in read_jsonl_file(self.__file_path):
                result.append(self.__model_cls.model_validate_json(line))
            return result

    def __serialize(self, obj: pydantic.BaseModel) -> str:
        """Return a one-line JSON-string that represent a specified object

        :param obj: object to serialize
        """

        model_dump = obj.model_dump_json()
        if '\n' in model_dump:
            raise RuntimeError('Invalid model serialization! Serialization logic must be changed!')
        return model_dump

    def _write_json(self, data: typing.Sequence[pydantic.BaseModel]) -> None:
        """Replace a file with a new set of inner objects.

        :param data: a new set of complete data to save
        """

        with self.__lock_manager.lock():
            with open(self.__file_path, "w", encoding="utf-8") as f:
                for d in data:
                    f.write(self.__serialize(d))
                    f.write("\n")

    def _append_json(self, data: pydantic.BaseModel) -> None:
        """Append a new object to a current set
        """

        with self.__lock_manager.lock():
            with open(self.__file_path, "a", encoding="utf-8") as f:
                f.write(self.__serialize(data))
                f.write("\n")

    def _write_single_obj_json(self, obj: pydantic.BaseModel) -> None:
        """Replace a file with a new object.

        :param obj: a new object to save
        """

        with self.__lock_manager.lock():
            with open(self.__file_path, "w", encoding="utf-8") as f:
                f.write(obj.model_dump_json())

    def _read_single_obj_json(self) -> pydantic.BaseModel:
        """Read an object."""

        with self.__lock_manager.lock():
            with open(self.__file_path, "r", encoding="utf-8") as f:
                file_data = f.read()
                return self.__model_cls.model_validate_json(file_data)  # type: ignore[no-any-return]

    def _init_data(self) -> str:
        """ Return a string that represent a default content for a new JSON-file
        """
        return ''

    def _ensure_file(self) -> None:
        """Check if there is a file and create an empty one if the file doesn't exist
        """

        with self.__lock_manager.lock():
            self.__file_path.parent.mkdir(parents=True, exist_ok=True)

            if not self.__file_path.exists():
                with open(self.__file_path, "a", encoding="utf-8") as f:
                    f.write(self._init_data())


class JsonTaskStorage(PlainTaskStorageProto, _BaseJsonEntityStorage):
    """Storage that saves :class:`.Task` objects"""

    def __init__(
        self,
        storage_id: uuid.UUID,
        data_dir: pathlib.Path,
        lock: StorageLock,
    ) -> None:
        """ Create a new task storage

        :param storage_id: idenitifies a storage this substorage is related to
        :param data_dir: absolute path to a directory where a storage file should be created
        :param lock: exclusive I/O lock
        """

        PlainTaskStorageProto.__init__(self)
        _BaseJsonEntityStorage.__init__(
            self,
            data_dir=data_dir,
            file_type=JsonFile.tasks,
            lock=lock,
        )

        self.__storage_id = storage_id

    def load_tasks(self) -> typing.List[Task]:
        """ :meth:`.PlainTaskStorageProto.load_tasks` method implementation
        """
        return self._read_json()

    def record_task(self, task: Task) -> None:
        """ :meth:`.PlainTaskStorageProto.record_task` method implementation
        """
        task.storage_origin = self.__storage_id
        self._append_json(task)


class JsonRecurrenceRuleStorage(PlainRecurrenceRuleStorageProto, _BaseJsonEntityStorage):
    """Storage that saves :class:`.RecurrenceRule` objects"""

    def __init__(
        self,
        data_dir: pathlib.Path,
        lock: StorageLock,
    ) -> None:
        """ Create a new rule storage

        :param data_dir: absolute path to a directory where a storage file should be created
        :param lock: exclusive I/O lock
        """

        PlainRecurrenceRuleStorageProto.__init__(self)
        _BaseJsonEntityStorage.__init__(
            self,
            data_dir=data_dir,
            file_type=JsonFile.recurrence_rules,
            lock=lock,
        )

    def load_recurrence_rules(self) -> typing.List[RecurrenceRule]:
        """ :meth:`.PlainTaskStorageProto.load_recurrence_rules` method implementation
        """

        return self._read_json()

    def record_recurrence_rule(self, rule: RecurrenceRule) -> None:
        """ :meth:`.PlainTaskStorageProto.record_recurrence_rule` method implementation
        """
        self._append_json(rule)


class JsonHistoryStorage(PlainStateHistoryStorageProto, _BaseJsonEntityStorage):
    """Storage that saves :class:`.StateUpdatedEvent` objects"""

    def __init__(
        self,
        storage_id: uuid.UUID,
        data_dir: pathlib.Path,
        lock: StorageLock,
    ) -> None:
        """ Create a new state-history storage

        :param storage_id: idenitifies a storage this substorage is related to
        :param data_dir: absolute path to a directory where a storage file should be created
        :param lock: exclusive I/O lock
        """

        PlainStateHistoryStorageProto.__init__(self)
        _BaseJsonEntityStorage.__init__(
            self,
            data_dir=data_dir,
            file_type=JsonFile.states_history,
            lock=lock,
        )

        self.__storage_id = storage_id

    def load_states_history(self) -> typing.List[StateUpdatedEvent]:
        """ :meth:`.PlainStateHistoryStorageProto.load_states_history` method implementation
        """
        return self._read_json()

    def find_events_for_task(self, task_id_query: typing.Union[uuid.UUID, str]) -> typing.List[StateUpdatedEvent]:
        """ :meth:`.PlainStateHistoryStorageProto.find_events_for_task` method implementation
        """
        return [e for e in self.load_states_history() if partial_uuid_select(e.task_id, task_id_query)]

    def record_history_event(self, event: StateUpdatedEvent) -> None:
        """ :meth:`.PlainStateHistoryStorageProto.record_history_event` method implementation
        """
        event.storage_origin = self.__storage_id
        self._append_json(event)


class JsonSettingsStorage(PlainSettingsStorageProto, _BaseJsonEntityStorage):
    """Storage that saves :class:`.ToDoStorageSettings` object"""

    def __init__(
        self,
        data_dir: pathlib.Path,
        expected_version: str,
        lock: StorageLock,
    ) -> None:
        """ Create a new state-history storage

        :param data_dir: absolute path to a directory where a storage file should be created
        :param lock: exclusive I/O lock
        """
        self.__expected_version = expected_version

        PlainSettingsStorageProto.__init__(self)
        _BaseJsonEntityStorage.__init__(
            self,
            data_dir=data_dir,
            file_type=JsonFile.settings,
            lock=lock
        )

        try:
            self.__settings: ToDoStorageSettings = self._read_single_obj_json()  # type: ignore[assignment]
        except pydantic.ValidationError as e:
            # sanity check
            scheme_version_name = 'scheme_version'

            if scheme_version_name not in ToDoStorageSettings.model_fields:
                raise RuntimeError('The "scheme_version" field is unkown to the model')

            err = e.errors()[0]

            if err['type'] == 'missing' and scheme_version_name in err['loc']:
                raise SchemeMigrationRequiredError(
                    'Looks like a previous version of DB spotted. Please try to update a scheme with the "update-db" '
                    'command (please, note a backup).'
                ) from e
            else:
                raise

        app_version = packaging.version.Version(__version__)
        # this removes suffixes like '-dev'
        app_version = packaging.version.Version(app_version.base_version)

        scheme_version = packaging.version.Version(self.scheme_version())
        # this removes suffixes like '-dev'
        scheme_version = packaging.version.Version(scheme_version.base_version)

        if scheme_version > app_version:
            # TODO: make it with the specific exception
            raise RuntimeError(
                "This is an outdated application which version is smaller then scheme's version. "
                f"Application version -- {app_version}; scheme version -- {scheme_version}."
            )

        if packaging.version.Version(self.__expected_version) > scheme_version:
            # TODO: make it with the specific exception
            raise RuntimeError(
                'There are migrations for this database. Please try to update a scheme with the "update-db" command '
                '(please, note a backup).'
            )

    def storage_id(self) -> uuid.UUID:
        """ :meth:`.PlainSettingsStorageProto.storage_id` method implementation
        """
        return self.__settings.id

    def scheme_version(self) -> str:
        # TODO: comments or to the PlainSettingsStorageProto
        return self.__settings.scheme_version

    def _init_data(self) -> str:
        """ This overriden :meth:`._BaseJsonEntityStorage._init_data` method that returns settings defaults
        """
        default_settings = ToDoStorageSettings(
            comment="JSON-file storage",
            scheme_version=self.__expected_version
        )

        return default_settings.model_dump_json()


__json_storage_scheme__ = 'json+file'


@register_api(__storage_registry__, __json_storage_scheme__)
class JsonStorage(PlainStorageProto):
    """JSON facade storage coordinating JsonTaskStorage, JsonRecurrenceRuleStorage, and JsonHistoryStorage."""

    def __init__(self, storage_uri: URI) -> None:
        """ Create a new storage

        :param storage_uri: storage settings
        """
        PlainStorageProto.__init__(self)

        if storage_uri.scheme != 'json+file':
            raise ValueError(f'Invalid storage scheme -- {storage_uri.scheme} ({__json_storage_scheme__} is expected)')

        if storage_uri.path is None:
            raise ValueError(f'A directory path was not specified with URI -- {storage_uri}')

        self.__data_dir = pathlib.Path('/') / pathlib.Path(storage_uri.path)

        if not self.__data_dir.is_absolute():
            RuntimeError('Data directory path must be an absolute')

        if self.__data_dir.exists() and not self.__data_dir.is_dir():
            raise ValueError(f'Storage directory exists and this is not a directory -- {self.__data_dir}')

        self.__lock = StorageLock(lock_file=(self.__data_dir / ".lock"))
        self.__se = JsonSettingsStorage(self.__data_dir, self.latest_migration(), lock=self.__lock)
        self.__ts = JsonTaskStorage(self.__se.storage_id(), self.__data_dir, lock=self.__lock)
        self.__rs = JsonRecurrenceRuleStorage(self.__data_dir, lock=self.__lock)
        self.__hs = JsonHistoryStorage(self.__se.storage_id(), self.__data_dir, lock=self.__lock)

        self.reinitialize_recurrency_states()

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

    def _settings(self) -> JsonSettingsStorage:
        """ :meth:`.PlainStorageProto._settings` method implementation
        """
        return self.__se

    @classmethod
    def create_storage(cls, storage_uri: URI) -> 'JsonStorage':
        """ :meth:`.ToDoStorageProto.create_storage` method implementation
        """
        return cls(storage_uri)

    @classmethod
    def latest_migration(cls) -> str:
        migrations = [str(x) for x in __json_migrations_registry__.ids()]
        migrations.sort(key=lambda x: packaging.version.Version(x))
        return migrations[-1]

    @classmethod
    def update_scheme(cls, scheme_uri: URI) -> str:
        """ :meth:`.ToDoStorageProto.update_scheme` method implementation
        """

        if scheme_uri.path is None:
            raise ValueError(f'A directory path was not specified with URI -- {scheme_uri}')

        storage_path = pathlib.Path('/') / pathlib.Path(scheme_uri.path)

        current_version = None
        with (storage_path / JsonFile.settings.value).open() as f:
            settings_json = json.load(f)
            if 'scheme_version' in settings_json:
                current_version = packaging.version.Version(settings_json['scheme_version'])
                # this removes suffixes like '-dev'
                current_version = packaging.version.Version(current_version.base_version)

        migrations = [str(x) for x in __json_migrations_registry__.ids()]
        migrations.sort(key=lambda x: packaging.version.Version(x))

        app_version = packaging.version.Version(__version__)
        # this removes suffixes like '-dev'
        app_version = packaging.version.Version(app_version.base_version)

        if current_version is not None and app_version < current_version:
            # TODO: copy to the main json implementation storage!
            # TODO: make it with the specific exception
            raise SchemeMigrationCallError(
                "This is an outdated application which version is smaller then scheme's version. "
                f"Application version -- {app_version}; scheme version -- {current_version}."
            )

        migrations_to_call = []

        for migration_id in migrations:

            next_version = packaging.version.Version(migration_id)

            if current_version is not None and current_version > next_version:
                continue

            if next_version > app_version:
                raise SchemeMigrationCallError('There are future migrations that are obviously unsupported')

            migrations_to_call.append(migration_id)

        if not migrations_to_call:
            raise RuntimeError('There are no migrations to call')

        for migration_id in migrations_to_call:
            Logger.info(f'Running the "{migration_id}" migration')

            migration_fn = __json_migrations_registry__.get(migration_id)
            migration_fn(storage_path)

        return migrations_to_call[-1]
