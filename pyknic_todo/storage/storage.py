# -*- coding: utf-8 -*-
# pyknic_todo/storage/storage.py
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

"""Storage layer and abstractions for pyknic-todo conforming to STORAGE.md."""

# TODO: document the code
# TODO: write tests for the code
# TODO: may be it is better to search with a search engine that works in conjuction with storage engine. This may help to:
#   - not to load JSON files multiple times!
#   - not to load everything from SQL-a-like storages

from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

from pyknic_todo.models import (
    EndCondition,
    RecurrenceRule,
    RecurrenceRuleDocument,
    StateHistoryDocument,
    StateHistoryEvent,
    Task,
    TaskDocument,
    get_utc_now_iso,
    VALID_STATUSES,
    VALID_PRIORITIES
)
from pyknic_todo.settings import Settings

from .proto import (
    AbstractTaskStorage,
    AbstractRecurrenceRuleStorage,
    AbstractHistoryStorage,
    AbstractStorage,
    TaskStorageUpdaterContext
)


DEFAULT_SETTINGS = Settings()
SCHEMA_VERSION = DEFAULT_SETTINGS.schema_version
DEFAULT_DATA_DIR = str(DEFAULT_SETTINGS.data_dir)


# =====================================================================
# JSON Storage Implementation (Hidden / Encapsulated)
# =====================================================================


class StorageLock:
    """Handles file-level and thread-level locking across storage operations."""

    def __init__(
        self,
        lock_file: str | Path,
        data_dir: Optional[str | Path] = None,
    ) -> None:
        self.lock_file = Path(lock_file).expanduser().resolve()
        self.data_dir = Path(data_dir).expanduser().resolve() if data_dir is not None else self.lock_file.parent
        self._thread_lock = threading.RLock()
        self._lock_fd: Optional[int] = None
        self._lock_depth: int = 0
        self._lock_is_exclusive: bool = False

    @contextmanager
    def lock(
        self,
        exclusive: bool = True,
        blocking: bool = True,
    ) -> Iterator[None]:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._thread_lock.acquire()
        try:
            op = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
            if not blocking:
                op |= fcntl.LOCK_NB

            if self._lock_depth > 0:
                if exclusive and not self._lock_is_exclusive:
                    if self._lock_fd is not None:
                        fcntl.flock(self._lock_fd, op)
                    self._lock_is_exclusive = True
                self._lock_depth += 1
                try:
                    yield
                finally:
                    self._lock_depth -= 1
                    if self._lock_depth == 0 and self._lock_fd is not None:
                        try:
                            fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
                        finally:
                            os.close(self._lock_fd)
                            self._lock_fd = None
                            self._lock_is_exclusive = False
                return

            fd = os.open(self.lock_file, os.O_CREAT | os.O_RDWR, 0o666)
            try:
                fcntl.flock(fd, op)
                self._lock_fd = fd
                self._lock_depth = 1
                self._lock_is_exclusive = exclusive
            except Exception:
                os.close(fd)
                raise

            try:
                yield
            finally:
                self._lock_depth -= 1
                if self._lock_depth == 0 and self._lock_fd is not None:
                    try:
                        fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
                    finally:
                        os.close(self._lock_fd)
                        self._lock_fd = None
                        self._lock_is_exclusive = False
        finally:
            self._thread_lock.release()


class BaseJsonEntityStorage:
    """Base storage handling JSON file persistence and synchronization for an entity."""

    def __init__(
        self,
        file_name: str,
        file_path: Optional[str | Path] = None,
        data_dir: Optional[str | Path] = None,
        settings: Optional[Settings] = None,
        lock: Optional[StorageLock] = None,
        lock_file: Optional[str | Path] = None,
    ) -> None:
        self.settings = settings or Settings()
        if data_dir is not None:
            self.data_dir = Path(data_dir).expanduser().resolve()
        else:
            self.data_dir = self.settings.data_dir.expanduser().resolve()

        self.file_path = (
            Path(file_path).expanduser().resolve()
            if file_path is not None
            else (self.data_dir / file_name)
        )

        if lock is not None:
            self.lock_manager = lock
        else:
            lf = (
                Path(lock_file).expanduser().resolve()
                if lock_file is not None
                else (self.data_dir / ".lock")
            )
            self.lock_manager = StorageLock(lock_file=lf, data_dir=self.data_dir)

        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_file()

    @property
    def lock_file(self) -> Path:
        return self.lock_manager.lock_file

    @property
    def _lock_depth(self) -> int:
        return self.lock_manager._lock_depth

    @property
    def _lock_is_exclusive(self) -> bool:
        return self.lock_manager._lock_is_exclusive

    @property
    def _lock_fd(self) -> Optional[int]:
        return self.lock_manager._lock_fd

    @property
    def _thread_lock(self) -> threading.RLock:
        return self.lock_manager._thread_lock

    @contextmanager
    def lock(
        self,
        exclusive: bool = True,
        blocking: bool = True,
    ) -> Iterator[None]:
        with self.lock_manager.lock(exclusive=exclusive, blocking=blocking):
            yield

    def _read_json(self, path: Optional[Path] = None) -> dict[str, Any]:
        target = Path(path) if path is not None else self.file_path
        with self.lock(exclusive=False):
            with open(target, "r", encoding="utf-8") as f:
                return json.load(f)  # type: ignore[no-any-return]

    def _write_json(self, path_or_data: Any, data: Optional[dict[str, Any]] = None) -> None:
        if data is None:
            target = self.file_path
            payload = path_or_data
        else:
            target = Path(path_or_data)
            payload = data

        with self.lock(exclusive=True):
            temp_path = target.with_suffix(f".tmp.{uuid.uuid4().hex[:6]}")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
                f.write("\n")
            temp_path.replace(target)

    def _ensure_file(self) -> None:
        raise NotImplementedError


BaseEntityStorage = BaseJsonEntityStorage


class JsonTaskStorage(AbstractTaskStorage, BaseJsonEntityStorage):
    """JSON file-based implementation of TaskStorage."""

    # TODO: make the write row-by-row, it will increase the speed of 'append' operations so as a search

    class UpdaterContext(TaskStorageUpdaterContext):
        # TODO: update docstring

        def __init__(self, storage: AbstractTaskStorage, id_query: str, query_full_match: bool = True):
            TaskStorageUpdaterContext.__init__(self)
            self.__storage = storage
            self.__all_tasks = self.__storage.load_tasks()
            self.__task = self.__find_task(id_query, full_match=query_full_match)

        def __find_task(self, id_query: str, full_match: bool = False) -> Task:
            # TODO: please note! there is a code that relay on exceptions int this code

            partial_match = []
            fully_matched = None
            for t in self.__all_tasks:
                if t.id.startswith(id_query):
                    if t.id == id_query:
                        if fully_matched is not None:
                            raise ValueError(f"Ambiguous task ID prefix '{id_query}'")
                        fully_matched = t
                    elif not full_match:
                        partial_match.append(t)

            if fully_matched is not None:
                return fully_matched

            if partial_match:
                if len(partial_match) > 1:
                    raise ValueError(f"Ambiguous task ID prefix '{id_query}', matches {len(partial_match)} tasks")
                return partial_match[0]

            raise KeyError(f"Task '{id_query}' not found")

        def __call__(self) -> Task:
            return self.__task

        def commit(self) -> None:
            self.__storage.save_tasks(self.__all_tasks)

    def __init__(
        self,
        file_path: Optional[str | Path] = None,
        data_dir: Optional[str | Path] = None,
        settings: Optional[Settings] = None,
        lock: Optional[StorageLock] = None,
        lock_file: Optional[str | Path] = None,
    ) -> None:
        super().__init__(
            file_name="tasks.json",
            file_path=file_path,
            data_dir=data_dir,
            settings=settings,
            lock=lock,
            lock_file=lock_file,
        )

    def _ensure_file(self) -> None:
        with self.lock(exclusive=True):
            if not self.file_path.exists():
                self._write_json(self.initial_document())

    # --- Representation ---

    def initial_document(self, client_id: Optional[str] = None) -> dict[str, Any]:
        cid = client_id or f"{self.settings.client_id_prefix}-{uuid.uuid4().hex[:12]}"
        return {
            "$schema_version": self.settings.schema_version,
            "client_id": cid,
            "updated_at": get_utc_now_iso(),
            "items": [],
        }

    def load_document(self) -> dict[str, Any]:
        return self._read_json()

    def save_document(self, data: dict[str, Any]) -> None:
        self._write_json(data)

    def load_document_model(self) -> TaskDocument:
        return TaskDocument(**self.load_document())

    # --- Reading ---

    def load_tasks(self) -> list[Task]:
        with self.lock(exclusive=False):
            data = self.load_document()
            return [Task(**x) for x in data.get("items", [])]

    # --- Writing ---

    def save_tasks(self, tasks: list[Task]) -> None:
        with self.lock(exclusive=True):
            data = self.load_document()
            data["items"] = [x.model_dump() for x in tasks]
            data["updated_at"] = get_utc_now_iso()
            self.save_document(data)

    def updater_context(self, id_query: str, query_full_match: bool = True) -> TaskStorageUpdaterContext:
        return JsonTaskStorage.UpdaterContext(self, id_query, query_full_match=query_full_match)

    def append_task(self, task: Task) -> None:
        # TODO: check that there is no duplicates (the same id)
        with self.lock(exclusive=True):
            tasks = self.load_tasks()
            tasks.append(task)
            self.save_tasks(tasks)


class JsonRecurrenceRuleStorage(AbstractRecurrenceRuleStorage, BaseJsonEntityStorage):
    """JSON file-based implementation of RecurrenceRuleStorage."""

    def __init__(
        self,
        file_path: Optional[str | Path] = None,
        data_dir: Optional[str | Path] = None,
        settings: Optional[Settings] = None,
        lock: Optional[StorageLock] = None,
        lock_file: Optional[str | Path] = None,
    ) -> None:
        super().__init__(
            file_name="recurrence_rules.json",
            file_path=file_path,
            data_dir=data_dir,
            settings=settings,
            lock=lock,
            lock_file=lock_file,
        )

    def _ensure_file(self) -> None:
        with self.lock(exclusive=True):
            if not self.file_path.exists():
                self._write_json(self.initial_document())

    # --- Representation ---

    def initial_document(self) -> dict[str, Any]:
        return {
            "$schema_version": self.settings.schema_version,
            "items": [],
        }

    def load_document(self) -> dict[str, Any]:
        return self._read_json()

    def save_document(self, data: dict[str, Any]) -> None:
        self._write_json(data)

    def load_document_model(self) -> RecurrenceRuleDocument:
        return RecurrenceRuleDocument(**self.load_document())

    # --- Reading ---

    def load_recurrence_rules(self) -> list[RecurrenceRule]:
        with self.lock(exclusive=False):
            data = self.load_document()
            return [RecurrenceRule(**x) for x in data.get("items", [])]  # type: ignore[no-any-return]

    # --- Writing ---

    def save_recurrence_rules(self, rules: list[RecurrenceRule]) -> None:
        with self.lock(exclusive=True):
            data = self.load_document()
            data["items"] = [x.model_dump() for x in rules]
            self.save_document(data)

    def append_recurrence_rule(self, rule: RecurrenceRule) -> None:
        # TODO: check that there is no duplicates (the same id)

        with self.lock(exclusive=True):
            rules = self.load_recurrence_rules()
            rules.append(rule)
            self.save_recurrence_rules(rules)


class JsonHistoryStorage(AbstractHistoryStorage, BaseJsonEntityStorage):
    """JSON file-based implementation of HistoryStorage."""

    def __init__(
        self,
        file_path: Optional[str | Path] = None,
        data_dir: Optional[str | Path] = None,
        settings: Optional[Settings] = None,
        lock: Optional[StorageLock] = None,
        lock_file: Optional[str | Path] = None,
    ) -> None:
        super().__init__(
            file_name="states_history.json",
            file_path=file_path,
            data_dir=data_dir,
            settings=settings,
            lock=lock,
            lock_file=lock_file,
        )

    def _ensure_file(self) -> None:
        with self.lock(exclusive=True):
            if not self.file_path.exists():
                self._write_json(self.initial_document())

    # --- Representation ---

    def initial_document(self) -> dict[str, Any]:
        return {
            "$schema_version": self.settings.schema_version,
            "events": [],
        }

    def load_document(self) -> dict[str, Any]:
        return self._read_json()

    def save_document(self, data: dict[str, Any]) -> None:
        self._write_json(data)

    def load_document_model(self) -> StateHistoryDocument:
        return StateHistoryDocument(**self.load_document())

    # --- Reading ---

    def load_history(self) -> list[StateHistoryEvent]:
        with self.lock(exclusive=False):
            data = self.load_document()
            return [StateHistoryEvent(**e) for e in data.get("events", [])]

    def find_events_for_task(self, task_id: str) -> list[StateHistoryEvent]:
        with self.lock(exclusive=False):
            return [e for e in self.load_history() if e.task_id == task_id]

    # --- Writing ---

    def save_history(self, events: list[StateHistoryEvent]) -> None:
        with self.lock(exclusive=True):
            data = self.load_document()
            data["events"] = [x.model_dump() for x in events]
            self.save_document(data)

    def record_history_event(self, event: StateHistoryEvent) -> None:
        with self.lock(exclusive=True):
            data = self.load_document()
            data.setdefault("events", []).append(event.model_dump())
            self.save_document(data)


class JsonStorage(StorageLock, AbstractStorage):
    """JSON facade storage coordinating JsonTaskStorage, JsonRecurrenceRuleStorage, and JsonHistoryStorage."""

    def __init__(
        self,
        data_dir: Optional[str | Path] = None,
        settings: Optional[Settings] = None,
        lock_file: Optional[str | Path] = None,
    ) -> None:
        if settings is not None:
            self.settings = settings
            if data_dir is not None:
                self.settings = self.settings.model_copy(update={"data_dir": Path(data_dir)})
        elif data_dir is not None:
            self.settings = Settings(data_dir=Path(data_dir))
        else:
            self.settings = Settings()

        self.data_dir = self.settings.data_dir.expanduser().resolve()
        self.lock_file = (
            Path(lock_file).expanduser().resolve()
            if lock_file is not None
            else (self.data_dir / ".lock")
        )
        super().__init__(lock_file=self.lock_file, data_dir=self.data_dir)

        self.tasks_file = self.data_dir / "tasks.json"
        self.recurrence_file = self.data_dir / "recurrence_rules.json"
        self.history_file = self.data_dir / "states_history.json"

        self._task_storage = JsonTaskStorage(
            file_path=self.tasks_file,
            data_dir=self.data_dir,
            settings=self.settings,
            lock=self,
        )
        self._recurrence_storage = JsonRecurrenceRuleStorage(
            file_path=self.recurrence_file,
            data_dir=self.data_dir,
            settings=self.settings,
            lock=self,
        )
        self._history_storage = JsonHistoryStorage(
            file_path=self.history_file,
            data_dir=self.data_dir,
            settings=self.settings,
            lock=self,
        )

        # Direct attribute aliases for backward compatibility
        self.task_storage = self._task_storage
        self.recurrence_storage = self._recurrence_storage
        self.history_storage = self._history_storage

    @property
    def tasks(self) -> JsonTaskStorage:
        return self._task_storage

    @property
    def recurrence_rules(self) -> JsonRecurrenceRuleStorage:
        return self._recurrence_storage

    @property
    def history(self) -> JsonHistoryStorage:
        return self._history_storage

    def _ensure_files(self) -> None:
        self.tasks._ensure_file()
        self.recurrence_rules._ensure_file()
        self.history._ensure_file()

    def _read_json(self, path: Path) -> dict[str, Any]:
        with self.lock(exclusive=False):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)  # type: ignore[no-any-return]

    def _write_json(self, path: Path, data: dict[str, Any]) -> None:
        with self.lock(exclusive=True):
            temp_path = path.with_suffix(f".tmp.{uuid.uuid4().hex[:6]}")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.write("\n")
            temp_path.replace(path)


# Backward compatibility aliases
TaskStorage = JsonTaskStorage
RecurrenceRuleStorage = JsonRecurrenceRuleStorage
RecurrenceStorage = JsonRecurrenceRuleStorage
HistoryStorage = JsonHistoryStorage
StateHistoryStorage = JsonHistoryStorage
Storage = JsonStorage


# =====================================================================
# Storage Factory
# =====================================================================


class StorageFactory:
    """Factory creating storage instances for different storage backends (e.g. JSON, SQL)."""

    _storage_backends: dict[str, Any] = {}
    _task_backends: dict[str, Any] = {}
    _recurrence_backends: dict[str, Any] = {}
    _history_backends: dict[str, Any] = {}

    @classmethod
    def register(
        cls,
        storage_type: str,
        storage_cls: type[AbstractStorage],
        task_cls: Optional[type[AbstractTaskStorage]] = None,
        recurrence_cls: Optional[type[AbstractRecurrenceRuleStorage]] = None,
        history_cls: Optional[type[AbstractHistoryStorage]] = None,
    ) -> None:
        key = storage_type.lower().strip()
        cls._storage_backends[key] = storage_cls
        if task_cls is not None:
            cls._task_backends[key] = task_cls
        if recurrence_cls is not None:
            cls._recurrence_backends[key] = recurrence_cls
        if history_cls is not None:
            cls._history_backends[key] = history_cls

    @classmethod
    def get_registered_types(cls) -> list[str]:
        return sorted(cls._storage_backends.keys())

    @classmethod
    def create_storage(
        cls,
        storage_type: Optional[str] = None,
        data_dir: Optional[str | Path] = None,
        settings: Optional[Settings] = None,
        **kwargs: Any,
    ) -> AbstractStorage:
        st = storage_type or (settings.storage_type if settings and hasattr(settings, "storage_type") else "json")
        key = st.lower().strip()
        if key not in cls._storage_backends:
            raise ValueError(
                f"Unsupported storage type '{st}'. Available: {cls.get_registered_types()}"
            )
        backend_cls = cls._storage_backends[key]
        return backend_cls(data_dir=data_dir, settings=settings, **kwargs)  # type: ignore[no-any-return]

    @classmethod
    def append_task_storage(
        cls,
        storage_type: Optional[str] = None,
        data_dir: Optional[str | Path] = None,
        settings: Optional[Settings] = None,
        **kwargs: Any,
    ) -> AbstractTaskStorage:
        st = storage_type or (settings.storage_type if settings and hasattr(settings, "storage_type") else "json")
        key = st.lower().strip()
        if key not in cls._task_backends:
            raise ValueError(
                f"Unsupported task storage type '{st}'. Available: {cls.get_registered_types()}"
            )
        backend_cls = cls._task_backends[key]
        return backend_cls(data_dir=data_dir, settings=settings, **kwargs)  # type: ignore[no-any-return]

    @classmethod
    def create_recurrence_storage(
        cls,
        storage_type: Optional[str] = None,
        data_dir: Optional[str | Path] = None,
        settings: Optional[Settings] = None,
        **kwargs: Any,
    ) -> AbstractRecurrenceRuleStorage:
        st = storage_type or (settings.storage_type if settings and hasattr(settings, "storage_type") else "json")
        key = st.lower().strip()
        if key not in cls._recurrence_backends:
            raise ValueError(
                f"Unsupported recurrence storage type '{st}'. Available: {cls.get_registered_types()}"
            )
        backend_cls = cls._recurrence_backends[key]
        return backend_cls(data_dir=data_dir, settings=settings, **kwargs)  # type: ignore[no-any-return]

    @classmethod
    def create_history_storage(
        cls,
        storage_type: Optional[str] = None,
        data_dir: Optional[str | Path] = None,
        settings: Optional[Settings] = None,
        **kwargs: Any,
    ) -> AbstractHistoryStorage:
        st = storage_type or (settings.storage_type if settings and hasattr(settings, "storage_type") else "json")
        key = st.lower().strip()
        if key not in cls._history_backends:
            raise ValueError(
                f"Unsupported history storage type '{st}'. Available: {cls.get_registered_types()}"
            )
        backend_cls = cls._history_backends[key]
        return backend_cls(data_dir=data_dir, settings=settings, **kwargs)  # type: ignore[no-any-return]


# Register default JSON backend
StorageFactory.register(
    "json",
    storage_cls=JsonStorage,
    task_cls=JsonTaskStorage,
    recurrence_cls=JsonRecurrenceRuleStorage,
    history_cls=JsonHistoryStorage,
)
