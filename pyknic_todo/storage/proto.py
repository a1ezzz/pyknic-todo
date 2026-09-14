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

import types
import typing
import uuid

from abc import ABCMeta, abstractmethod

from pyknic_todo.models import RecurrenceRule, StateHistoryEvent, Task, get_utc_now_iso, VALID_STATUSES
from pyknic_todo.settings import Settings


class TaskStorageUpdaterContext(metaclass=ABCMeta):
    """This abstract class helps to update a single task and helps to hide implementation routine. """

    def __enter__(self) -> typing.Self:
        """Enter this context."""

        return self

    def __exit__(
        self,
        exc_type: typing.Optional[typing.Type[BaseException]],
        exc_val: typing.Optional[BaseException],
        exc_tb: typing.Optional[types.TracebackType]
    ) -> None:
        """Exit this context."""
        pass

    @abstractmethod
    def __call__(self) -> Task:
        """Return a task this updater is changing."""
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def commit(self) -> None:
        """Save changes for a single task. (May be called multiple times)"""
        # TODO: there is a consistency issue -- this context may be saved, but a related structures (like 'StateHistoryEvent') may be missing =(
        raise NotImplementedError('This method is abstract')


class AbstractTaskStorage(metaclass=ABCMeta):
    """Abstract interface for task storage backends."""
    # TODO: is there should be some clean-up method (deleted tasks removing)? -- please note synchronization!

    @abstractmethod
    def load_tasks(self) -> list[Task]:
        """Load all tasks as dictionaries."""
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def save_tasks(self, tasks: list[Task]) -> None:
        """Save tasks list."""
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def updater_context(self, id_query: str, query_full_match: bool = True) -> TaskStorageUpdaterContext:
        """Return a context that helps to update a single task that was found by the specified criteria
        """
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def append_task(self, task: Task) -> None:
        """Append a new task in a storage"""
        raise NotImplementedError('This method is abstract')


class AbstractRecurrenceRuleStorage(metaclass=ABCMeta):
    """Abstract interface for recurrence rule storage backends."""
    # TODO: is the "updater_context" method require?
    # TODO: is there should be some clean-up method for orphaned rules (rules without tasks)?

    @abstractmethod
    def load_recurrence_rules(self) -> list[RecurrenceRule]:
        """Load all recurrence rules as dictionaries."""
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def save_recurrence_rules(self, rules: list[RecurrenceRule]) -> None:
        """Save recurrence rules list."""
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def append_recurrence_rule(self, rule: RecurrenceRule) -> None:
        """Create and persist a new recurrence rule."""
        raise NotImplementedError('This method is abstract')


class AbstractHistoryStorage(metaclass=ABCMeta):
    """Abstract interface for state history storage backends."""
    # TODO: is there should be some clean-up method for orphaned events (events without tasks)?

    @abstractmethod
    def load_history(self) -> list[StateHistoryEvent]:
        """Load all history events as dictionaries."""
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def save_history(self, events: list[StateHistoryEvent]) -> None:
        """Save history events list."""
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def record_history_event(self, event: StateHistoryEvent) -> None:
        """Record a state change event."""
        raise NotImplementedError('This method is abstract')

    @abstractmethod
    def find_events_for_task(self, task_id: str) -> list[StateHistoryEvent]:
        """Find history events for a given task ID."""
        raise NotImplementedError('This method is abstract')


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
        # TODO: it must be persistent!
        return str(uuid.uuid4())

    def load_tasks(self) -> list[Task]:
        return self.tasks.load_tasks()

    def save_tasks(self, tasks: list[Task]) -> None:
        self.tasks.save_tasks(tasks)

    def load_recurrence_rules(self) -> list[dict[str, typing.Any]]:
        return [x.model_dump() for x in self.recurrence_rules.load_recurrence_rules()]

    def save_recurrence_rules(self, rules: list[RecurrenceRule]) -> None:
        self.recurrence_rules.save_recurrence_rules(rules)

    def load_history(self) -> list[StateHistoryEvent]:
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

    @abstractmethod
    def storage_settings(self) -> typing.Optional[Settings]:
        ... 

    def append_task(
        self,
        title: str,
        description: str = "",
        priority: typing.Optional[str] = None,
        status: typing.Optional[str] = None,
        due_date: typing.Optional[str] = None,
        tags: typing.Optional[list[str]] = None,
        project_id: typing.Optional[str] = None,
    ) -> dict[str, typing.Any]:
        settings = self.storage_settings() or Settings()

        with self.lock(exclusive=True):
            task = Task.create(
                title=title,
                description=description,
                priority=priority or settings.default_priority,
                status=status or settings.default_status,
                due_date=due_date,
                tags=tags,
                project_id=project_id,
            )

            self.tasks.append_task(task)

            new_task = task.model_dump()

            self.history.record_history_event(
                StateHistoryEvent.create(
                    task_id=new_task["id"],
                    new_state={"status": new_task["status"]},
                    actor_client_id=self.get_client_id(),
                    comment="Created via CLI",
                )
            )
            return new_task

    def set_task_status(
        self,
        task_id_query: str,
        new_status: str,
        comment: typing.Optional[str] = None,
    ) -> dict[str, typing.Any]:
        with self.lock(exclusive=True):

            if new_status not in VALID_STATUSES:
                raise ValueError(f"Invalid status '{new_status}'. Valid statuses: {sorted(VALID_STATUSES)}")

            with self.tasks.updater_context(task_id_query, query_full_match=False) as tc:
                task = tc()

                now = get_utc_now_iso()

                task.status = new_status  # type: ignore[assignment]
                task.version = int(task.version or 1) + 1
                task.updated_at = now
                if new_status == "done":
                    task.completed_at = now
                elif task.completed_at:
                    task.completed_at = None

                if new_status == "deleted":
                    task.deleted_at = now
                elif task.deleted_at:
                    task.deleted_at = None

                tc.commit()

                self.history.record_history_event(
                    StateHistoryEvent.create(
                        task_id=task.id,
                        new_state={"status": new_status},
                        actor_client_id=self.get_client_id(),
                        comment=comment or f"Status changed to {new_status} via CLI",
                    )
                )

                return task.model_dump()

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

            rule = RecurrenceRule.create(
                    schedule_type=schedule_type,
                    schedule_expression=schedule_expression,
                    end_condition_type=end_condition_type,
                    until_date=until_date,
                    max_occurrences=max_occurrences,
                )
            self.recurrence_rules.append_recurrence_rule(rule)

            with self.tasks.updater_context(task_id_query, query_full_match=False) as tc:
                task = tc()

                task.recurrence_rule_id = rule.id
                task.version = int(task.version or 1) + 1
                task.updated_at = get_utc_now_iso()

                tc.commit()
                return task.model_dump(), rule.model_dump()  # TODO: ugly!
