# -*- coding: utf-8 -*-
# pyknic_todo/storage/plain.py
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
# TODO: refactor this

import abc
import types
import typing
import uuid

from pyknic_todo.models import Task, TaskStatus, RecurrenceRule, StateHistoryEvent, todo_models_now

from .proto import ToDoStorageProto


class TaskStorageUpdaterContext(metaclass=abc.ABCMeta):
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

    @abc.abstractmethod
    def __call__(self) -> Task:
        """Return a task this updater is changing."""
        raise NotImplementedError('This method is abstract')

    @abc.abstractmethod
    def commit(self) -> None:
        """Save changes for a single task. (May be called multiple times)"""
        # TODO: there is a consistency issue -- this context may be saved, but a related structures (like 'StateHistoryEvent') may be missing =(
        raise NotImplementedError('This method is abstract')


class AbstractTaskStorage(metaclass=abc.ABCMeta):
    """Abstract interface for task storage backends."""
    # TODO: is there should be some clean-up method (deleted tasks removing)? -- please note synchronization!
    # TODO: rename

    @abc.abstractmethod
    def load_tasks(self) -> list[Task]:
        """Load all tasks as dictionaries."""
        raise NotImplementedError('This method is abstract')

    @abc.abstractmethod
    def save_tasks(self, tasks: list[Task]) -> None:
        """Save tasks list."""
        raise NotImplementedError('This method is abstract')

    @abc.abstractmethod
    def updater_context(self, id_query: typing.Union[uuid.UUID, str], query_full_match: bool = True) -> TaskStorageUpdaterContext:
        """Return a context that helps to update a single task that was found by the specified criteria
        """
        raise NotImplementedError('This method is abstract')

    @abc.abstractmethod
    def append_task(self, task: Task) -> None:
        """Append a new task in a storage"""
        raise NotImplementedError('This method is abstract')


class AbstractRecurrenceRuleStorage(metaclass=abc.ABCMeta):
    """Abstract interface for recurrence rule storage backends."""
    # TODO: is there should be some clean-up method for orphaned rules (rules without tasks)?
    # TODO: rename

    @abc.abstractmethod
    def load_recurrence_rules(self) -> list[RecurrenceRule]:
        """Load all recurrence rules as dictionaries."""
        raise NotImplementedError('This method is abstract')

    @abc.abstractmethod
    def save_recurrence_rules(self, rules: list[RecurrenceRule]) -> None:
        """Save recurrence rules list."""
        raise NotImplementedError('This method is abstract')

    @abc.abstractmethod
    def append_recurrence_rule(self, rule: RecurrenceRule) -> None:
        """Create and persist a new recurrence rule."""
        raise NotImplementedError('This method is abstract')


class AbstractHistoryStorage(metaclass=abc.ABCMeta):
    """Abstract interface for state history storage backends."""
    # TODO: is there should be some clean-up method for orphaned events (events without tasks)?
    # TODO: rename -- it is not a general history, but a state related one

    @abc.abstractmethod
    def load_history(self) -> list[StateHistoryEvent]:
        """Load all history events as dictionaries."""
        raise NotImplementedError('This method is abstract')

    @abc.abstractmethod
    def save_history(self, events: list[StateHistoryEvent]) -> None:
        # TODO: remove this
        """Save history events list."""
        raise NotImplementedError('This method is abstract')

    @abc.abstractmethod
    def record_history_event(self, event: StateHistoryEvent) -> None:
        """Record a state change event."""
        raise NotImplementedError('This method is abstract')

    @abc.abstractmethod
    def find_events_for_task(self, task_id_query: typing.Union[uuid.UUID, str]) -> list[StateHistoryEvent]:
        """Find history events for a given task ID."""
        raise NotImplementedError('This method is abstract')

    @abc.abstractmethod
    def task_latest_status(self, task_id_query: typing.Union[uuid.UUID, str]) -> TaskStatus:
        raise NotImplementedError('This method is abstract')


class AbstractStorage(ToDoStorageProto, metaclass=abc.ABCMeta):
    """Abstract facade interface coordinating tasks, recurrence rules, and history."""
    # TODO: rename -- it is not a general history, but a state related one
    # TODO: it is better to hide storage implementations sudh as tasks and make them protected

    @property
    @abc.abstractmethod
    def _tasks(self) -> AbstractTaskStorage:
        """Task storage component."""
        raise NotImplementedError('This method is abstract')

    @property
    @abc.abstractmethod
    def _recurrence_rules(self) -> AbstractRecurrenceRuleStorage:
        """Recurrence rule storage component."""
        raise NotImplementedError('This method is abstract')

    @property
    @abc.abstractmethod
    def _history(self) -> AbstractHistoryStorage:
        """History storage component."""
        raise NotImplementedError('This method is abstract')

    @abc.abstractmethod
    def lock(
        self,
        exclusive: bool = True,
        blocking: bool = True,
    ) -> typing.ContextManager[None]:
        """Acquire synchronization lock for storage operations."""
        raise NotImplementedError('This method is abstract')

    def load_tasks(self) -> list[Task]:
        return self._tasks.load_tasks()

    def save_tasks(self, tasks: list[Task]) -> None:
        self._tasks.save_tasks(tasks)

    def load_recurrence_rules(self) -> list[RecurrenceRule]:
        return self._recurrence_rules.load_recurrence_rules()

    def save_recurrence_rules(self, rules: list[RecurrenceRule]) -> None:
        self._recurrence_rules.save_recurrence_rules(rules)

    def load_history(self) -> list[StateHistoryEvent]:
        return self._history.load_history()

    def record_history_event(self, event: StateHistoryEvent) -> None:
        self._history.record_history_event(event)

    def append_task(self, task: Task) -> None:

        with self.lock(exclusive=True):
            self._tasks.append_task(task)

            self._history.record_history_event(
                StateHistoryEvent(
                    task_id=task.id,
                    next_state=TaskStatus.new,
                )
            )

    def task_status(self, task_id_query: typing.Union[uuid.UUID, str]) -> TaskStatus:
        # TODO: real implementation must be faster!

        with self._tasks.updater_context(task_id_query, query_full_match=False) as tc:  # TODO: may be it is better to have read-only analog
            return self._history.task_latest_status(tc().id)

    def set_task_status(
        self,
        task_id_query: typing.Union[uuid.UUID, str],
        new_status: TaskStatus,
        comment: typing.Optional[str] = None,
    ) -> Task:
        with self.lock(exclusive=True):

            casted_id = str(task_id_query.id) if isinstance(task_id_query, Task) else str(task_id_query)

            with self._tasks.updater_context(casted_id, query_full_match=False) as tc:
                task = tc()

                now = todo_models_now()

                if new_status in (TaskStatus.done, TaskStatus.deleted):

                    task.version += 1

                    if new_status == TaskStatus.done:
                        task.completed_at = now
                    elif task.completed_at:
                        task.completed_at = None

                    if new_status == TaskStatus.deleted:
                        task.deleted_at = now
                    elif task.deleted_at:
                        task.deleted_at = None

                    tc.commit()

                self._history.record_history_event(
                    StateHistoryEvent(
                        task_id=task.id,
                        next_state=TaskStatus(new_status),
                        comment=comment or ""
                    )
                )

                return task

    def set_task_recurrence(
        self,
        task_id_query: typing.Union[uuid.UUID, str],
        rule: typing.Optional[RecurrenceRule] = None
    ) -> Task:
        with self.lock(exclusive=True):

            with self._tasks.updater_context(task_id_query, query_full_match=False) as tc:
                task = tc()

                if rule:
                    self._recurrence_rules.append_recurrence_rule(rule)
                    task.recurrence_rule_id = rule.id
                else:
                    task.recurrence_rule_id = None

                task.version += 1
                task.updated_at = todo_models_now()

                tc.commit()
                return task
