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

from .models import EndCondition, RecurrenceRule, StateHistoryEvent, Task
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


class Storage:
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
        self.tasks_file = self.data_dir / "tasks.json"
        self.recurrence_file = self.data_dir / "recurrence_rules.json"
        self.history_file = self.data_dir / "states_history.json"
        self.lock_file = Path(lock_file) if lock_file is not None else (self.data_dir / ".lock")
        self._thread_lock = threading.RLock()
        self._lock_fd: Optional[int] = None
        self._lock_depth: int = 0
        self._lock_is_exclusive: bool = False
        self._ensure_files()

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

    def _ensure_files(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with self.lock(exclusive=True):
            if not self.tasks_file.exists():
                client_id = f"{self.settings.client_id_prefix}-{uuid.uuid4().hex[:12]}"
                initial_tasks: dict[str, Any] = {
                    "$schema_version": self.settings.schema_version,
                    "client_id": client_id,
                    "updated_at": get_utc_now_iso(),
                    "items": [],
                }
                self._write_json(self.tasks_file, initial_tasks)

            if not self.recurrence_file.exists():
                initial_recurrence: dict[str, Any] = {
                    "$schema_version": self.settings.schema_version,
                    "items": [],
                }
                self._write_json(self.recurrence_file, initial_recurrence)

            if not self.history_file.exists():
                initial_history: dict[str, Any] = {
                    "$schema_version": self.settings.schema_version,
                    "events": [],
                }
                self._write_json(self.history_file, initial_history)

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
        with self.lock(exclusive=False):
            data = self._read_json(self.tasks_file)
            return data.get("client_id", f"{self.settings.client_id_prefix}-default")  # type: ignore[no-any-return]

    def load_tasks(self) -> list[dict[str, Any]]:
        with self.lock(exclusive=False):
            data = self._read_json(self.tasks_file)
            return data.get("items", [])  # type: ignore[no-any-return]

    def save_tasks(self, tasks: list[dict[str, Any]]) -> None:
        with self.lock(exclusive=True):
            data = self._read_json(self.tasks_file)
            data["items"] = tasks
            data["updated_at"] = get_utc_now_iso()
            self._write_json(self.tasks_file, data)

    def load_recurrence_rules(self) -> list[dict[str, Any]]:
        with self.lock(exclusive=False):
            data = self._read_json(self.recurrence_file)
            return data.get("items", [])  # type: ignore[no-any-return]

    def save_recurrence_rules(self, rules: list[dict[str, Any]]) -> None:
        with self.lock(exclusive=True):
            data = self._read_json(self.recurrence_file)
            data["items"] = rules
            self._write_json(self.recurrence_file, data)

    def load_history(self) -> list[dict[str, Any]]:
        with self.lock(exclusive=False):
            data = self._read_json(self.history_file)
            return data.get("events", [])  # type: ignore[no-any-return]

    def record_history_event(
        self,
        task_id: str,
        new_state: dict[str, Any],
        comment: Optional[str] = None,
    ) -> dict[str, Any]:
        with self.lock(exclusive=True):
            data = self._read_json(self.history_file)
            event_obj = StateHistoryEvent(
                id=f"evt-{uuid.uuid4().hex[:8]}",
                task_id=task_id,
                timestamp=get_utc_now_iso(),
                actor_client_id=self.get_client_id(),
                new_state=new_state,
                comment=comment or "",
            )
            event = event_obj.model_dump()
            data.setdefault("events", []).append(event)
            self._write_json(self.history_file, data)
            return event

    def find_task(self, query: str) -> Optional[dict[str, Any]]:
        with self.lock(exclusive=False):
            tasks = self.load_tasks()
            # Exact match
            for task in tasks:
                if task.get("id") == query:
                    return task
            # Prefix match
            matches = [t for t in tasks if t.get("id", "").startswith(query)]
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                raise ValueError(
                    f"Ambiguous task ID prefix '{query}', matches {len(matches)} tasks"
                )
            return None

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
            new_task = task_obj.model_dump()

            tasks = self.load_tasks()
            tasks.append(new_task)
            self.save_tasks(tasks)

            self.record_history_event(
                task_id=task_id,
                new_state={"status": task_status},
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
            if new_status not in VALID_STATUSES:
                raise ValueError(f"Invalid status '{new_status}'. Valid statuses: {sorted(VALID_STATUSES)}")

            tasks = self.load_tasks()
            matched = [i for i, t in enumerate(tasks) if t.get("id") == task_id_query]
            if not matched:
                matched = [i for i, t in enumerate(tasks) if t.get("id", "").startswith(task_id_query)]
            if not matched:
                raise KeyError(f"Task '{task_id_query}' not found")
            if len(matched) > 1:
                raise ValueError(f"Ambiguous task ID prefix '{task_id_query}', matches {len(matched)} tasks")

            target_idx = matched[0]
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

            self.record_history_event(
                task_id=task["id"],
                new_state={"status": new_status},
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
            if schedule_type not in VALID_SCHEDULE_TYPES:
                raise ValueError(f"Invalid schedule_type '{schedule_type}'. Valid: {sorted(VALID_SCHEDULE_TYPES)}")
            if end_condition_type not in VALID_END_CONDITIONS:
                raise ValueError(
                    f"Invalid end_condition_type '{end_condition_type}'. Valid: {sorted(VALID_END_CONDITIONS)}"
                )

            tasks = self.load_tasks()
            matched = [i for i, t in enumerate(tasks) if t.get("id") == task_id_query]
            if not matched:
                matched = [i for i, t in enumerate(tasks) if t.get("id", "").startswith(task_id_query)]
            if not matched:
                raise KeyError(f"Task '{task_id_query}' not found")
            if len(matched) > 1:
                raise ValueError(f"Ambiguous task ID prefix '{task_id_query}', matches {len(matched)} tasks")

            target_idx = matched[0]
            task = tasks[target_idx]

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
            rule = rule_obj.model_dump()

            rules = self.load_recurrence_rules()
            rules.append(rule)
            self.save_recurrence_rules(rules)

            task["recurrence_rule_id"] = rule_id
            task["version"] = int(task.get("version", 1)) + 1
            task["updated_at"] = now
            tasks[target_idx] = task
            self.save_tasks(tasks)

            return task, rule
