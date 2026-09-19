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

import abc
import typing
import uuid

from pyknic.lib.uri import URI

from pyknic_todo.models import Task, RecurrenceRule, StateHistoryEvent, TaskStatus


class ToDoStorageProto(metaclass=abc.ABCMeta):
    """Abstract facade interface coordinating tasks, recurrence rules, and history."""

    # TODO: there should be some clean-up method (but please note synchronization!):
    #   - deleted tasks removing
    #   - rules without tasks
    #   - history events without tasks
    #   - outdated history events

    @classmethod
    @abc.abstractmethod
    def create_storage(cls, storage_uri: URI) -> 'ToDoStorageProto':
        # TODO: docs + test
        raise NotImplementedError('This method is abstract')

    @abc.abstractmethod
    def load_tasks(self) -> list[Task]:
        """Load all tasks."""
        raise NotImplementedError('This method is abstract')

    def save_tasks(self, tasks: list[Task]) -> None:
        """Replace tasks and save them.

        :param tasks: a new set of tasks (previous tasks will be discared)
        """
        # TODO: pretty rough method. Should be replaced in a future with more specific functions
        raise NotImplementedError('This method is abstract')

    def load_recurrence_rules(self) -> list[RecurrenceRule]:
        """Load all recurrence rules."""
        raise NotImplementedError('This method is abstract')

    def save_recurrence_rules(self, rules: list[RecurrenceRule]) -> None:
        """Replace recurrence rules and save them.

        :param rules: a new set of rules (previous rules will be discared)
        """
        # TODO: pretty rough method. Should be replaced in a future with more specific functions
        raise NotImplementedError('This method is abstract')

    def load_history(self) -> list[StateHistoryEvent]:
        """Load all history events."""
        raise NotImplementedError('This method is abstract')

    def record_history_event(self, event: StateHistoryEvent) -> None:
        """Record a state change event.

        :param event: a new event to save
        """
        raise NotImplementedError('This method is abstract')

    def append_task(self, task: Task) -> None:
        """Append a new task. A new state ('new') for this task will be kept in a history automatically.

        :param task: a task to save
        """
        raise NotImplementedError('This method is abstract')

    def task_status(self, task_id_query: typing.Union[uuid.UUID, str]) -> TaskStatus:
        """Return latest task status

        :param task_id_query: a task identifier (a partial uuid submittion is supported)
        """
        raise NotImplementedError('This method is abstract')

    def set_task_status(
        self,
        task_id_query: typing.Union[uuid.UUID, str],
        new_status: TaskStatus,
        comment: typing.Optional[str] = None,
    ) -> Task:
        """Update task status.

        :param task_id_query: a task identifier to update (a partial uuid submittion is supported)
        :param new_status: a status to set

        :return: a task which status was updated
        """
        raise NotImplementedError('This method is abstract')

    def set_task_recurrence(
        self,
        task_id_query: typing.Union[uuid.UUID, str],
        rule: typing.Optional[RecurrenceRule] = None
    ) -> Task:
        """Set recurrence rule for the task.

        :param task_id_query: a task identifier to update (a partial uuid submittion is supported)
        :param rule: a new recurrence rule for a task. If None, then recurrence will be disabled.
        """
        raise NotImplementedError('This method is abstract')
