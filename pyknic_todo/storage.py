"""Storage layer for pyknic-todo JSON data files conforming to STORAGE.md."""

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

from .models import (
    EndCondition,
    RecurrenceRule,
    RecurrenceRuleDocument,
    StateHistoryDocument,
    StateHistoryEvent,
    Task,
    TaskDocument,
)
from .settings import Settings

DEFAULT_SETTINGS = Settings()
SCHEMA_VERSION = DEFAULT_SETTINGS.schema_version
DEFAULT_DATA_DIR = str(DEFAULT_SETTINGS.data_dir)

VALID_STATUSES = {
    "new",
    "pending",
    "in_progress",
    "done",
    "cancelled",
    "skipped",
    "deleted",
}

VALID_PRIORITIES = {"low", "medium", "high", "urgent"}
VALID_SCHEDULE_TYPES = {"rrule", "cron"}
VALID_END_CONDITIONS = {"never", "until_date", "count"}


def get_utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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


class BaseEntityStorage:
    """Base storage handling JSON persistence and synchronization for a single entity file."""

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


class TaskStorage(BaseEntityStorage):
    """Responsible for reading, writing, and representing Task entities and tasks.json."""

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

    @staticmethod
    def to_model(data: dict[str, Any]) -> Task:
        return Task(**data)

    @staticmethod
    def from_model(model: Task) -> dict[str, Any]:
        return model.model_dump()

    def represent(self, task: Task | dict[str, Any]) -> dict[str, Any]:
        if isinstance(task, Task):
            return self.from_model(task)
        return self.to_model(task).model_dump()

    def load_document(self) -> dict[str, Any]:
        return self._read_json()

    def save_document(self, data: dict[str, Any]) -> None:
        self._write_json(data)

    def load_document_model(self) -> TaskDocument:
        return TaskDocument(**self.load_document())

    # --- Reading ---

    def get_client_id(self) -> str:
        with self.lock(exclusive=False):
            data = self.load_document()
            return data.get("client_id", f"{self.settings.client_id_prefix}-default")  # type: ignore[no-any-return]

    def load_tasks(self) -> list[dict[str, Any]]:
        with self.lock(exclusive=False):
            data = self.load_document()
            return data.get("items", [])  # type: ignore[no-any-return]

    def load_task_models(self) -> list[Task]:
        return [self.to_model(t) for t in self.load_tasks()]

    def find_task(self, query: str) -> Optional[dict[str, Any]]:
        with self.lock(exclusive=False):
            tasks = self.load_tasks()
            for task in tasks:
                if task.get("id") == query:
                    return task
            matches = [t for t in tasks if t.get("id", "").startswith(query)]
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                raise ValueError(
                    f"Ambiguous task ID prefix '{query}', matches {len(matches)} tasks"
                )
            return None

    def find_task_model(self, query: str) -> Optional[Task]:
        task = self.find_task(query)
        return self.to_model(task) if task is not None else None

    def find_task_index(self, tasks: list[dict[str, Any]], query: str) -> int:
        matched = [i for i, t in enumerate(tasks) if t.get("id") == query]
        if not matched:
            matched = [i for i, t in enumerate(tasks) if t.get("id", "").startswith(query)]
        if not matched:
            raise KeyError(f"Task '{query}' not found")
        if len(matched) > 1:
            raise ValueError(f"Ambiguous task ID prefix '{query}', matches {len(matched)} tasks")
        return matched[0]

    def find_task_or_raise(self, query: str) -> dict[str, Any]:
        tasks = self.load_tasks()
        idx = self.find_task_index(tasks, query)
        return tasks[idx]

    # --- Writing ---

    def save_tasks(self, tasks: list[dict[str, Any]]) -> None:
        with self.lock(exclusive=True):
            data = self.load_document()
            data["items"] = tasks
            data["updated_at"] = get_utc_now_iso()
            self.save_document(data)

    def create_task(
        self,
        title: str,
        description: str = "",
        priority: Optional[str] = None,
        status: Optional[str] = None,
        due_date: Optional[str] = None,
        tags: Optional[list[str]] = None,
        project_id: Optional[str] = None,
    ) -> dict[str, Any]:
        with self.lock(exclusive=True):
            task_status = status or self.settings.default_status
            task_priority = priority or self.settings.default_priority

            if task_status not in VALID_STATUSES:
                raise ValueError(f"Invalid status '{task_status}'. Valid statuses: {sorted(VALID_STATUSES)}")
            if task_priority not in VALID_PRIORITIES:
                raise ValueError(f"Invalid priority '{task_priority}'. Valid priorities: {sorted(VALID_PRIORITIES)}")

            now = get_utc_now_iso()
            task_id = str(uuid.uuid4())
            task_obj = Task(
                id=task_id,
                project_id=project_id,
                title=title.strip(),
                description=description.strip() if description else "",
                status=task_status,  # type: ignore[arg-type]
                priority=task_priority,  # type: ignore[arg-type]
                due_date=due_date,
                tags=tags or [],
                recurrence_rule_id=None,
                parent_recurrence_task_id=None,
                version=1,
                created_at=now,
                updated_at=now,
                completed_at=now if task_status == "done" else None,
                deleted_at=now if task_status == "deleted" else None,
            )
            new_task = self.from_model(task_obj)

            tasks = self.load_tasks()
            tasks.append(new_task)
            self.save_tasks(tasks)
            return new_task

    def set_task_status(
        self,
        task_id_query: str,
        new_status: str,
    ) -> dict[str, Any]:
        with self.lock(exclusive=True):
            if new_status not in VALID_STATUSES:
                raise ValueError(f"Invalid status '{new_status}'. Valid statuses: {sorted(VALID_STATUSES)}")

            tasks = self.load_tasks()
            target_idx = self.find_task_index(tasks, task_id_query)
            task = tasks[target_idx]
            now = get_utc_now_iso()

            task["status"] = new_status
            task["version"] = int(task.get("version", 1)) + 1
            task["updated_at"] = now
            if new_status == "done":
                task["completed_at"] = now
            elif task.get("completed_at"):
                task["completed_at"] = None

            if new_status == "deleted":
                task["deleted_at"] = now
            elif task.get("deleted_at"):
                task["deleted_at"] = None

            tasks[target_idx] = task
            self.save_tasks(tasks)
            return task

    def set_recurrence_rule_id(
        self,
        task_id_query: str,
        recurrence_rule_id: str,
    ) -> dict[str, Any]:
        with self.lock(exclusive=True):
            tasks = self.load_tasks()
            target_idx = self.find_task_index(tasks, task_id_query)
            task = tasks[target_idx]
            now = get_utc_now_iso()

            task["recurrence_rule_id"] = recurrence_rule_id
            task["version"] = int(task.get("version", 1)) + 1
            task["updated_at"] = now
            tasks[target_idx] = task
            self.save_tasks(tasks)
            return task


class RecurrenceRuleStorage(BaseEntityStorage):
    """Responsible for reading, writing, and representing RecurrenceRule entities and recurrence_rules.json."""

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

    @staticmethod
    def to_model(data: dict[str, Any]) -> RecurrenceRule:
        return RecurrenceRule(**data)

    @staticmethod
    def from_model(model: RecurrenceRule) -> dict[str, Any]:
        return model.model_dump()

    def represent(self, rule: RecurrenceRule | dict[str, Any]) -> dict[str, Any]:
        if isinstance(rule, RecurrenceRule):
            return self.from_model(rule)
        return self.to_model(rule).model_dump()

    def load_document(self) -> dict[str, Any]:
        return self._read_json()

    def save_document(self, data: dict[str, Any]) -> None:
        self._write_json(data)

    def load_document_model(self) -> RecurrenceRuleDocument:
        return RecurrenceRuleDocument(**self.load_document())

    # --- Reading ---

    def load_recurrence_rules(self) -> list[dict[str, Any]]:
        with self.lock(exclusive=False):
            data = self.load_document()
            return data.get("items", [])  # type: ignore[no-any-return]

    def load_rules(self) -> list[dict[str, Any]]:
        return self.load_recurrence_rules()

    def load_rule_models(self) -> list[RecurrenceRule]:
        return [self.to_model(r) for r in self.load_recurrence_rules()]

    def find_rule(self, rule_id: str) -> Optional[dict[str, Any]]:
        with self.lock(exclusive=False):
            for rule in self.load_recurrence_rules():
                if rule.get("id") == rule_id:
                    return rule
            return None

    def find_rule_model(self, rule_id: str) -> Optional[RecurrenceRule]:
        rule = self.find_rule(rule_id)
        return self.to_model(rule) if rule is not None else None

    # --- Writing ---

    def save_recurrence_rules(self, rules: list[dict[str, Any]]) -> None:
        with self.lock(exclusive=True):
            data = self.load_document()
            data["items"] = rules
            self.save_document(data)

    def save_rules(self, rules: list[dict[str, Any]]) -> None:
        self.save_recurrence_rules(rules)

    def create_rule(
        self,
        schedule_type: str,
        schedule_expression: str,
        end_condition_type: str = "never",
        until_date: Optional[str] = None,
        max_occurrences: Optional[int] = None,
    ) -> dict[str, Any]:
        with self.lock(exclusive=True):
            if schedule_type not in VALID_SCHEDULE_TYPES:
                raise ValueError(f"Invalid schedule_type '{schedule_type}'. Valid: {sorted(VALID_SCHEDULE_TYPES)}")
            if end_condition_type not in VALID_END_CONDITIONS:
                raise ValueError(
                    f"Invalid end_condition_type '{end_condition_type}'. Valid: {sorted(VALID_END_CONDITIONS)}"
                )

            rule_id = f"rec-rule-{uuid.uuid4().hex[:8]}"
            now = get_utc_now_iso()
            rule_obj = RecurrenceRule(
                id=rule_id,
                schedule_type=schedule_type,  # type: ignore[arg-type]
                schedule_expression=schedule_expression.strip(),
                end_condition=EndCondition(
                    type=end_condition_type,  # type: ignore[arg-type]
                    until_date=until_date,
                    max_occurrences=max_occurrences,
                ),
                created_at=now,
            )
            rule = self.from_model(rule_obj)

            rules = self.load_recurrence_rules()
            rules.append(rule)
            self.save_recurrence_rules(rules)
            return rule


class HistoryStorage(BaseEntityStorage):
    """Responsible for reading, writing, and representing StateHistoryEvent entities and states_history.json."""

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

    @staticmethod
    def to_model(data: dict[str, Any]) -> StateHistoryEvent:
        return StateHistoryEvent(**data)

    @staticmethod
    def from_model(model: StateHistoryEvent) -> dict[str, Any]:
        return model.model_dump()

    def represent(self, event: StateHistoryEvent | dict[str, Any]) -> dict[str, Any]:
        if isinstance(event, StateHistoryEvent):
            return self.from_model(event)
        return self.to_model(event).model_dump()

    def load_document(self) -> dict[str, Any]:
        return self._read_json()

    def save_document(self, data: dict[str, Any]) -> None:
        self._write_json(data)

    def load_document_model(self) -> StateHistoryDocument:
        return StateHistoryDocument(**self.load_document())

    # --- Reading ---

    def load_history(self) -> list[dict[str, Any]]:
        with self.lock(exclusive=False):
            data = self.load_document()
            return data.get("events", [])  # type: ignore[no-any-return]

    def load_events(self) -> list[dict[str, Any]]:
        return self.load_history()

    def load_event_models(self) -> list[StateHistoryEvent]:
        return [self.to_model(e) for e in self.load_history()]

    def find_events_for_task(self, task_id: str) -> list[dict[str, Any]]:
        with self.lock(exclusive=False):
            return [e for e in self.load_history() if e.get("task_id") == task_id]

    # --- Writing ---

    def save_history(self, events: list[dict[str, Any]]) -> None:
        with self.lock(exclusive=True):
            data = self.load_document()
            data["events"] = events
            self.save_document(data)

    def save_events(self, events: list[dict[str, Any]]) -> None:
        self.save_history(events)

    def record_history_event(
        self,
        task_id: str,
        new_state: dict[str, Any],
        actor_client_id: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> dict[str, Any]:
        with self.lock(exclusive=True):
            data = self.load_document()
            client_id = actor_client_id or f"{self.settings.client_id_prefix}-default"
            event_obj = StateHistoryEvent(
                id=f"evt-{uuid.uuid4().hex[:8]}",
                task_id=task_id,
                timestamp=get_utc_now_iso(),
                actor_client_id=client_id,
                new_state=new_state,
                comment=comment or "",
            )
            event = self.from_model(event_obj)
            data.setdefault("events", []).append(event)
            self.save_document(data)
            return event

    def record_event(
        self,
        task_id: str,
        new_state: dict[str, Any],
        actor_client_id: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> dict[str, Any]:
        return self.record_history_event(
            task_id=task_id,
            new_state=new_state,
            actor_client_id=actor_client_id,
            comment=comment,
        )


# Aliases for convenience
RecurrenceStorage = RecurrenceRuleStorage
StateHistoryStorage = HistoryStorage


class Storage(StorageLock):
    """Facade storage coordinating TaskStorage, RecurrenceRuleStorage, and HistoryStorage."""

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

        self.task_storage = TaskStorage(
            file_path=self.tasks_file,
            data_dir=self.data_dir,
            settings=self.settings,
            lock=self,
        )
        self.tasks = self.task_storage

        self.recurrence_storage = RecurrenceRuleStorage(
            file_path=self.recurrence_file,
            data_dir=self.data_dir,
            settings=self.settings,
            lock=self,
        )
        self.recurrence_rules = self.recurrence_storage

        self.history_storage = HistoryStorage(
            file_path=self.history_file,
            data_dir=self.data_dir,
            settings=self.settings,
            lock=self,
        )
        self.history = self.history_storage

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

    def get_client_id(self) -> str:
        return self.tasks.get_client_id()

    def load_tasks(self) -> list[dict[str, Any]]:
        return self.tasks.load_tasks()

    def save_tasks(self, tasks: list[dict[str, Any]]) -> None:
        self.tasks.save_tasks(tasks)

    def load_recurrence_rules(self) -> list[dict[str, Any]]:
        return self.recurrence_rules.load_recurrence_rules()

    def save_recurrence_rules(self, rules: list[dict[str, Any]]) -> None:
        self.recurrence_rules.save_recurrence_rules(rules)

    def load_history(self) -> list[dict[str, Any]]:
        return self.history.load_history()

    def record_history_event(
        self,
        task_id: str,
        new_state: dict[str, Any],
        comment: Optional[str] = None,
    ) -> dict[str, Any]:
        return self.history.record_history_event(
            task_id=task_id,
            new_state=new_state,
            actor_client_id=self.get_client_id(),
            comment=comment,
        )

    def find_task(self, query: str) -> Optional[dict[str, Any]]:
        return self.tasks.find_task(query)

    def create_task(
        self,
        title: str,
        description: str = "",
        priority: Optional[str] = None,
        status: Optional[str] = None,
        due_date: Optional[str] = None,
        tags: Optional[list[str]] = None,
        project_id: Optional[str] = None,
    ) -> dict[str, Any]:
        with self.lock(exclusive=True):
            new_task = self.tasks.create_task(
                title=title,
                description=description,
                priority=priority,
                status=status,
                due_date=due_date,
                tags=tags,
                project_id=project_id,
            )
            self.history.record_history_event(
                task_id=new_task["id"],
                new_state={"status": new_task["status"]},
                actor_client_id=self.get_client_id(),
                comment="Created via CLI",
            )
            return new_task

    def set_task_status(
        self,
        task_id_query: str,
        new_status: str,
        comment: Optional[str] = None,
    ) -> dict[str, Any]:
        with self.lock(exclusive=True):
            task = self.tasks.set_task_status(
                task_id_query=task_id_query,
                new_status=new_status,
            )
            self.history.record_history_event(
                task_id=task["id"],
                new_state={"status": new_status},
                actor_client_id=self.get_client_id(),
                comment=comment or f"Status changed to {new_status} via CLI",
            )
            return task

    def set_task_recurrence(
        self,
        task_id_query: str,
        schedule_type: str,
        schedule_expression: str,
        end_condition_type: str = "never",
        until_date: Optional[str] = None,
        max_occurrences: Optional[int] = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        with self.lock(exclusive=True):
            # Validate task query first to avoid creating orphaned rules
            self.tasks.find_task_or_raise(task_id_query)

            rule = self.recurrence_rules.create_rule(
                schedule_type=schedule_type,
                schedule_expression=schedule_expression,
                end_condition_type=end_condition_type,
                until_date=until_date,
                max_occurrences=max_occurrences,
            )
            task = self.tasks.set_recurrence_rule_id(
                task_id_query=task_id_query,
                recurrence_rule_id=rule["id"],
            )
            return task, rule
