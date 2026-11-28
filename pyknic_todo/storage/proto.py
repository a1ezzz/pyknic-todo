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
from pyknic.lib.verify import verify_value

from pyknic_todo.models import Task, RecurrenceRule, StateUpdatedEvent, TaskStatus, Project


class SchemeMigrationRequiredError(Exception):
    """ This exception is raised when a scheme migration is required.
    """
    pass


class SchemeMigrationCallError(Exception):
    """ This exception is raised when a scheme migration fails to execute.
    """
    pass


class ToDoStorageProto(metaclass=abc.ABCMeta):
    """Abstract facade interface coordinating tasks, recurrence rules, and history."""

    @classmethod
    @abc.abstractmethod
    def create_storage(cls, storage_uri: URI) -> 'ToDoStorageProto':
        """Create a new storage by URI

        :param storage_uri: URI defines storage settings
        """
        raise NotImplementedError('This method is abstract')

    @abc.abstractmethod
    def storage_id(self) -> uuid.UUID:
        """ Return this storage identifier
        """
        raise NotImplementedError('This method is abstract')

    @abc.abstractmethod
    def load_tasks(self) -> list[Task]:
        """Load all tasks."""
        raise NotImplementedError('This method is abstract')

    @abc.abstractmethod
    def load_recurrence_rules(self) -> list[RecurrenceRule]:
        """Load all recurrence rules."""
        raise NotImplementedError('This method is abstract')

    @abc.abstractmethod
    def load_states_history(self) -> list[StateUpdatedEvent]:
        """Load all history events."""
        raise NotImplementedError('This method is abstract')

    @abc.abstractmethod
    def load_projects(self) -> list[Project]:
        """Load all projects."""
        raise NotImplementedError('This method is abstract')

    @abc.abstractmethod
    def record_task(self, task: Task) -> None:
        """Append a new task or update a previous one. A new state ('pending') for the task will be kept in a history
        automatically.

        :param task: a task to save
        """
        raise NotImplementedError('This method is abstract')

    @abc.abstractmethod
    def record_history_event(self, event: StateUpdatedEvent) -> None:
        """Record a state change event.

        :param event: a new event to save
        """
        # TODO: remove from public proto-spec! This is poisonous since may not update
        #  state_id and update_dt in a task. Use the set_task_status method instead!
        #
        raise NotImplementedError('This method is abstract')

    @abc.abstractmethod
    def record_recurrence_rule(self, rule: RecurrenceRule) -> None:
        """Append a new recurrence rule.

        :param rules: a new rule to append
        """
        raise NotImplementedError('This method is abstract')

    def record_project(self, project: Project) -> None:
        """Append a new project.

        :param project: a new project to append
        """
        raise NotImplementedError('This method is abstract')

    @abc.abstractmethod
    def task_status(self, task_id_query: typing.Union[uuid.UUID, str]) -> TaskStatus:
        """Return latest task status

        :param task_id_query: a task identifier (a partial uuid submittion is supported)
        """
        raise NotImplementedError('This method is abstract')

    @abc.abstractmethod
    @verify_value(new_status=lambda x: x != TaskStatus.skipped)
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

    @abc.abstractmethod
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

    @abc.abstractmethod
    def purge_data(
        self,
        remove_deleted_task: bool,
        remove_completed_task: bool,
        reduce_history: bool,
        remove_empty_projects: bool
    ) -> int:
        """ Clean and return a count of removed redundant rows.

        :param remove_deleted_task: whether to remove deleted tasks
        :param remove_completed_task: whether to remove completed tasks
        :param reduce_history: whether to remove change history
        :param remove_empty_projects: whether to remove projects without tasks
        """
        raise NotImplementedError('This method is abstract')

    @classmethod
    @abc.abstractmethod
    def update_scheme(cls, scheme_uri: URI) -> str:
        """ Update current scheme and return latest applied version
        """
        raise NotImplementedError('This method is abstract')

    @classmethod
    @abc.abstractmethod
    def latest_migration(cls) -> str:
        """ Return lastest migration this application/scheme required
        """
        raise NotImplementedError('This method is abstract')
