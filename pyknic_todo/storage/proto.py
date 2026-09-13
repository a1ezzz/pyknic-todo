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
# TODO: refactor this

import typing

from abc import ABCMeta, abstractmethod

from pyknic_todo.models import RecurrenceRule, StateHistoryEvent, Task
from pyknic_todo.search import find_task_or_raise


class AbstractTaskStorage(metaclass=ABCMeta):
    """Abstract interface for task storage backends."""

    @abstractmethod
    def load_tasks(self) -> list[Task]:
        """Load all tasks as dictionaries."""
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def save_tasks(self, tasks: list[Task]) -> None:
        """Save tasks list."""
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def create_task(
        self,
        title: str,
        description: str = "",
        priority: typing.Optional[str] = None,
        status: typing.Optional[str] = None,
        due_date: typing.Optional[str] = None,
        tags: typing.Optional[list[str]] = None,
        project_id: typing.Optional[str] = None,
    ) -> dict[str, typing.Any]:
        """Create a new task and persist it."""
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def set_task_status(
        self,
        task_id_query: str,
        new_status: str,
    ) -> dict[str, typing.Any]:
        """Update status of a task matching the query."""
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def set_recurrence_rule_id(
        self,
        task_id_query: str,
        recurrence_rule_id: str,
    ) -> dict[str, typing.Any]:
        """Attach a recurrence rule ID to a task matching the query."""
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def get_client_id(self) -> str:
        """Get the client ID associated with the storage."""
        raise NotImplementedError('This method is abstract')


class AbstractRecurrenceRuleStorage(metaclass=ABCMeta):
    """Abstract interface for recurrence rule storage backends."""

    @abstractmethod
    def load_recurrence_rules(self) -> list[dict[str, typing.Any]]:
        """Load all recurrence rules as dictionaries."""
        raise NotImplementedError('This method is abstract')

    def load_rules(self) -> list[dict[str, typing.Any]]:
        return self.load_recurrence_rules()

    @abstractmethod
    def save_recurrence_rules(self, rules: list[dict[str, typing.Any]]) -> None:
        """Save recurrence rules list."""
        raise NotImplementedError('This method is abstract')

    def save_rules(self, rules: list[dict[str, typing.Any]]) -> None:
        self.save_recurrence_rules(rules)

    @abstractmethod
    def create_rule(
        self,
        schedule_type: str,
        schedule_expression: str,
        end_condition_type: str = "never",
        until_date: typing.Optional[str] = None,
        max_occurrences: typing.Optional[int] = None,
    ) -> dict[str, typing.Any]:
        """Create and persist a new recurrence rule."""
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def find_rule(self, rule_id: str) -> typing.Optional[dict[str, typing.Any]]:
        """Find a recurrence rule by ID."""
        raise NotImplementedError('This method is abstract')

    def load_rule_models(self) -> list[RecurrenceRule]:
        return [RecurrenceRule(**r) for r in self.load_recurrence_rules()]

    def find_rule_model(self, rule_id: str) -> typing.Optional[RecurrenceRule]:
        rule = self.find_rule(rule_id)
        return RecurrenceRule(**rule) if rule is not None else None


class AbstractHistoryStorage(metaclass=ABCMeta):
    """Abstract interface for state history storage backends."""

    @abstractmethod
    def load_history(self) -> list[dict[str, typing.Any]]:
        """Load all history events as dictionaries."""
        raise NotImplementedError('This method is abstract')

    def load_events(self) -> list[dict[str, typing.Any]]:
        return self.load_history()

    @abstractmethod
    def save_history(self, events: list[dict[str, typing.Any]]) -> None:
        """Save history events list."""
        raise NotImplementedError('This method is abstract')

    def save_events(self, events: list[dict[str, typing.Any]]) -> None:
        self.save_history(events)

    @abstractmethod
    def record_history_event(
        self,
        task_id: str,
        new_state: dict[str, typing.Any],
        actor_client_id: typing.Optional[str] = None,
        comment: typing.Optional[str] = None,
    ) -> dict[str, typing.Any]:
        """Record a state change event."""
        raise NotImplementedError('This method is abstract')

    def record_event(
        self,
        task_id: str,
        new_state: dict[str, typing.Any],
        actor_client_id: typing.Optional[str] = None,
        comment: typing.Optional[str] = None,
    ) -> dict[str, typing.Any]:
        return self.record_history_event(
            task_id=task_id,
            new_state=new_state,
            actor_client_id=actor_client_id,
            comment=comment,
        )

    @abstractmethod
    def find_events_for_task(self, task_id: str) -> list[dict[str, typing.Any]]:
        """Find history events for a given task ID."""
        raise NotImplementedError('This method is abstract')

    def load_event_models(self) -> list[StateHistoryEvent]:
        return [StateHistoryEvent(**e) for e in self.load_history()]


class AbstractStorage(metaclass=ABCMeta):
    """Abstract facade interface coordinating tasks, recurrence rules, and history."""

    @property
    @abstractmethod
    def tasks(self) -> AbstractTaskStorage:
        """Task storage component."""
        raise NotImplementedError('This method is abstract')

    @property
    @abstractmethod
    def recurrence_rules(self) -> AbstractRecurrenceRuleStorage:
        """Recurrence rule storage component."""
        raise NotImplementedError('This method is abstract')

    @property
    @abstractmethod
    def history(self) -> AbstractHistoryStorage:
        """History storage component."""
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def lock(
        self,
        exclusive: bool = True,
        blocking: bool = True,
    ) -> typing.ContextManager[None]:
        """Acquire synchronization lock for storage operations."""
        raise NotImplementedError('This method is abstract')

    # Common coordination methods
    def get_client_id(self) -> str:
        return self.tasks.get_client_id()

    def load_tasks(self) -> list[Task]:
        return self.tasks.load_tasks()

    def save_tasks(self, tasks: list[Task]) -> None:
        self.tasks.save_tasks(tasks)

    def load_recurrence_rules(self) -> list[dict[str, typing.Any]]:
        return self.recurrence_rules.load_recurrence_rules()

    def save_recurrence_rules(self, rules: list[dict[str, typing.Any]]) -> None:
        self.recurrence_rules.save_recurrence_rules(rules)

    def load_history(self) -> list[dict[str, typing.Any]]:
        return self.history.load_history()

    def record_history_event(
        self,
        task_id: str,
        new_state: dict[str, typing.Any],
        comment: typing.Optional[str] = None,
    ) -> dict[str, typing.Any]:
        return self.history.record_history_event(
            task_id=task_id,
            new_state=new_state,
            actor_client_id=self.get_client_id(),
            comment=comment,
        )

    def create_task(
        self,
        title: str,
        description: str = "",
        priority: typing.Optional[str] = None,
        status: typing.Optional[str] = None,
        due_date: typing.Optional[str] = None,
        tags: typing.Optional[list[str]] = None,
        project_id: typing.Optional[str] = None,
    ) -> dict[str, typing.Any]:
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
        comment: typing.Optional[str] = None,
    ) -> dict[str, typing.Any]:
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
        until_date: typing.Optional[str] = None,
        max_occurrences: typing.Optional[int] = None,
    ) -> tuple[dict[str, typing.Any], dict[str, typing.Any]]:
        with self.lock(exclusive=True):

            find_task_or_raise(self.tasks.load_tasks(), task_id_query)  # TODO: it is better to do something with the task that was found

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
