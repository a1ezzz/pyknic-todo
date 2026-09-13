# -*- coding: utf-8 -*-
# pyknic_todo/storage/proto.py
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

# TODO: document the code
# TODO: write tests for the code


from abc import ABC, abstractmethod
from contextlib import contextmanager
import fcntl
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, ContextManager, Iterator, Optional

from pyknic_todo.models import (
    EndCondition,
    RecurrenceRule,
    RecurrenceRuleDocument,
    StateHistoryDocument,
    StateHistoryEvent,
    Task,
    TaskDocument,
)
from pyknic_todo.settings import Settings

# =====================================================================
# Abstract Base Classes
# =====================================================================


class AbstractTaskStorage(ABC):
    """Abstract interface for task storage backends."""

    @abstractmethod
    def load_tasks(self) -> list[dict[str, Any]]:
        """Load all tasks as dictionaries."""
        ...

    @abstractmethod
    def save_tasks(self, tasks: list[dict[str, Any]]) -> None:
        """Save tasks list."""
        ...

    @abstractmethod
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
        """Create a new task and persist it."""
        ...

    @abstractmethod
    def set_task_status(
        self,
        task_id_query: str,
        new_status: str,
    ) -> dict[str, Any]:
        """Update status of a task matching the query."""
        ...

    @abstractmethod
    def set_recurrence_rule_id(
        self,
        task_id_query: str,
        recurrence_rule_id: str,
    ) -> dict[str, Any]:
        """Attach a recurrence rule ID to a task matching the query."""
        ...

    @abstractmethod
    def find_task(self, query: str) -> Optional[dict[str, Any]]:
        """Find a task by exact ID or unique prefix."""
        ...

    @abstractmethod
    def find_task_or_raise(self, query: str) -> dict[str, Any]:
        """Find a task by exact ID or prefix, raising KeyError or ValueError."""
        ...

    @abstractmethod
    def get_client_id(self) -> str:
        """Get the client ID associated with the storage."""
        ...

    # Representation methods
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

    def load_task_models(self) -> list[Task]:
        return [self.to_model(t) for t in self.load_tasks()]

    def find_task_model(self, query: str) -> Optional[Task]:
        task = self.find_task(query)
        return self.to_model(task) if task is not None else None


class AbstractRecurrenceRuleStorage(ABC):
    """Abstract interface for recurrence rule storage backends."""

    @abstractmethod
    def load_recurrence_rules(self) -> list[dict[str, Any]]:
        """Load all recurrence rules as dictionaries."""
        ...

    def load_rules(self) -> list[dict[str, Any]]:
        return self.load_recurrence_rules()

    @abstractmethod
    def save_recurrence_rules(self, rules: list[dict[str, Any]]) -> None:
        """Save recurrence rules list."""
        ...

    def save_rules(self, rules: list[dict[str, Any]]) -> None:
        self.save_recurrence_rules(rules)

    @abstractmethod
    def create_rule(
        self,
        schedule_type: str,
        schedule_expression: str,
        end_condition_type: str = "never",
        until_date: Optional[str] = None,
        max_occurrences: Optional[int] = None,
    ) -> dict[str, Any]:
        """Create and persist a new recurrence rule."""
        ...

    @abstractmethod
    def find_rule(self, rule_id: str) -> Optional[dict[str, Any]]:
        """Find a recurrence rule by ID."""
        ...

    # Representation methods
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

    def load_rule_models(self) -> list[RecurrenceRule]:
        return [self.to_model(r) for r in self.load_recurrence_rules()]

    def find_rule_model(self, rule_id: str) -> Optional[RecurrenceRule]:
        rule = self.find_rule(rule_id)
        return self.to_model(rule) if rule is not None else None


class AbstractHistoryStorage(ABC):
    """Abstract interface for state history storage backends."""

    @abstractmethod
    def load_history(self) -> list[dict[str, Any]]:
        """Load all history events as dictionaries."""
        ...

    def load_events(self) -> list[dict[str, Any]]:
        return self.load_history()

    @abstractmethod
    def save_history(self, events: list[dict[str, Any]]) -> None:
        """Save history events list."""
        ...

    def save_events(self, events: list[dict[str, Any]]) -> None:
        self.save_history(events)

    @abstractmethod
    def record_history_event(
        self,
        task_id: str,
        new_state: dict[str, Any],
        actor_client_id: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> dict[str, Any]:
        """Record a state change event."""
        ...

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

    @abstractmethod
    def find_events_for_task(self, task_id: str) -> list[dict[str, Any]]:
        """Find history events for a given task ID."""
        ...

    # Representation methods
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

    def load_event_models(self) -> list[StateHistoryEvent]:
        return [self.to_model(e) for e in self.load_history()]


class AbstractStorage(ABC):
    """Abstract facade interface coordinating tasks, recurrence rules, and history."""

    @property
    @abstractmethod
    def tasks(self) -> AbstractTaskStorage:
        """Task storage component."""
        ...

    @property
    @abstractmethod
    def recurrence_rules(self) -> AbstractRecurrenceRuleStorage:
        """Recurrence rule storage component."""
        ...

    @property
    @abstractmethod
    def history(self) -> AbstractHistoryStorage:
        """History storage component."""
        ...

    @abstractmethod
    def lock(
        self,
        exclusive: bool = True,
        blocking: bool = True,
    ) -> ContextManager[None]:
        """Acquire synchronization lock for storage operations."""
        ...

    # Common coordination methods
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


AbstractRecurrenceStorage = AbstractRecurrenceRuleStorage
AbstractStateHistoryStorage = AbstractHistoryStorage
