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

"""Basic sorage layer and abstractions for pyknic-todo conforming to STORAGE.md."""

import abc
import datetime
import typing
import uuid

import dateutil.rrule

from pyknic.lib.tasks.scheduler.cron_source import CronSchedule
from pyknic.lib.verify import verify_value

from pyknic_todo.models import Task, TaskStatus, RecurrenceRule, StateUpdatedEvent, todo_models_now
from pyknic_todo.models import RecurrenceScheduleType, Project

from .proto import ToDoStorageProto
from .helpers import partial_uuid_select, exact_one_task


class PlainTaskStorageProto(metaclass=abc.ABCMeta):
    """Abstract interface for task storage backends."""

    @abc.abstractmethod
    def load_tasks(self) -> list[Task]:
        """Load all tasks."""
        raise NotImplementedError('This method is abstract')

    def record_task(self, task: Task) -> None:
        """Save a change (a new or updated task)"""
        raise NotImplementedError('This method is abstract')


class PlainRecurrenceRuleStorageProto(metaclass=abc.ABCMeta):
    """Abstract interface for recurrence rule storage backends."""

    @abc.abstractmethod
    def load_recurrence_rules(self) -> list[RecurrenceRule]:
        """Load all recurrence rules."""
        raise NotImplementedError('This method is abstract')

    @abc.abstractmethod
    def record_recurrence_rule(self, rule: RecurrenceRule) -> None:
        """Persist a recurrence rule.

        :param rule: a new rule to add
        """
        raise NotImplementedError('This method is abstract')


class PlainStateHistoryStorageProto(metaclass=abc.ABCMeta):
    """Abstract interface for state history storage backends."""

    @abc.abstractmethod
    def load_states_history(self) -> list[StateUpdatedEvent]:
        """Load all history events."""
        raise NotImplementedError('This method is abstract')

    @abc.abstractmethod
    def record_history_event(self, event: StateUpdatedEvent) -> None:
        """Record a state change event.

        :param event: a new event to save
        """
        raise NotImplementedError('This method is abstract')

    def find_events_for_task(self, task_id_query: typing.Union[uuid.UUID, str]) -> list[StateUpdatedEvent]:
        """Find history events for a given task ID.

        :param task_id_query: a task identifier to update (a partial uuid submittion is supported)
        """

        return [e for e in self.load_states_history() if partial_uuid_select(e.task_id, task_id_query)]


class PlainProjectStorageProto(metaclass=abc.ABCMeta):
    """Abstract interface for project storage backends."""

    @abc.abstractmethod
    def load_projects(self) -> list[Project]:
        """Load all projects."""
        raise NotImplementedError('This method is abstract')

    @abc.abstractmethod
    def record_project(self, project: Project) -> None:
        """Append a new project.

        :param project: a new project to append
        """
        raise NotImplementedError('This method is abstract')


class PlainSettingsStorageProto(metaclass=abc.ABCMeta):
    """Abstract interface for state history storage backends."""

    @abc.abstractmethod
    def storage_id(self) -> uuid.UUID:
        """ Return this storage identifier
        """
        raise NotImplementedError('This method is abstract')


class PlainStorageProto(ToDoStorageProto, metaclass=abc.ABCMeta):
    """Abstract facade interface coordinating tasks, recurrence rules, and history."""

    @abc.abstractmethod
    def _tasks(self) -> PlainTaskStorageProto:
        """Task storage component."""
        raise NotImplementedError('This method is abstract')

    @abc.abstractmethod
    def _recurrence_rules(self) -> PlainRecurrenceRuleStorageProto:
        """Recurrence rule storage component."""
        raise NotImplementedError('This method is abstract')

    @abc.abstractmethod
    def _history(self) -> PlainStateHistoryStorageProto:
        """History storage component."""
        raise NotImplementedError('This method is abstract')

    @abc.abstractmethod
    def _settings(self) -> PlainSettingsStorageProto:
        """Settings storage component."""
        raise NotImplementedError('This method is abstract')

    @abc.abstractmethod
    def _project(self) -> PlainProjectStorageProto:
        """Project storage component."""
        raise NotImplementedError('This method is abstract')

    def storage_id(self) -> uuid.UUID:
        """:meth:`.ToDoStorageProto.storage_id` implementation."""
        return self._settings().storage_id()

    def load_tasks(self) -> list[Task]:
        """:meth:`.ToDoStorageProto.load_tasks` implementation."""

        # TODO: this definitely requires a caching!
        filtered_tasks: typing.Dict[uuid.UUID, Task] = dict()

        for t in self._tasks().load_tasks():
            prev_t = filtered_tasks.get(t.id)
            if not prev_t:
                filtered_tasks[t.id] = t
                continue
            elif prev_t.updated_at <= t.updated_at and prev_t.version < t.version:
                filtered_tasks[t.id] = t
                continue
            elif prev_t.updated_at >= t.updated_at and prev_t.version > t.version:
                continue

            raise RuntimeError(
                'Unsupported state spotted -- "updated_at" and "version" fields mismatch internal logic. '
                f'The ID of a problematic task is -- {t.id})'
            )

        return list(filtered_tasks.values())

    def load_recurrence_rules(self) -> list[RecurrenceRule]:
        """:meth:`.ToDoStorageProto.load_recurrence_rules` implementation."""
        return self._recurrence_rules().load_recurrence_rules()

    def load_states_history(self) -> list[StateUpdatedEvent]:
        """:meth:`.ToDoStorageProto.load_states_history` implementation."""
        return self._history().load_states_history()

    def record_history_event(self, event: StateUpdatedEvent) -> None:
        """:meth:`.ToDoStorageProto.record_history_event` implementation."""
        self._history().record_history_event(event)

    def record_task(self, task: Task) -> None:
        """:meth:`.ToDoStorageProto.record_task` implementation."""

        if task.state_id is None:
            state_update = StateUpdatedEvent(
                task_id=task.id,
                next_state=TaskStatus.pending,
            )
            self._history().record_history_event(state_update)
            task.state_id = state_update.id
        else:
            task.updated_at = todo_models_now()
            task.version += 1

        self._tasks().record_task(task)

    def record_recurrence_rule(self, rule: RecurrenceRule) -> None:
        """:meth:`.ToDoStorageProto.record_recurrence_rule` implementation."""
        self._recurrence_rules().record_recurrence_rule(rule)

    def load_projects(self) -> list[Project]:
        """:meth:`.ToDoStorageProto.load_projects` implementation."""

        # TODO: this definitely requires a caching!
        filtered_projects: typing.Dict[uuid.UUID, Project] = dict()

        for p in self._project().load_projects():
            prev_p = filtered_projects.get(p.id)
            if not prev_p:
                filtered_projects[p.id] = p
                continue
            elif prev_p.updated_at <= p.updated_at and prev_p.version < p.version:
                filtered_projects[p.id] = p
                continue
            elif prev_p.updated_at > p.updated_at and prev_p.version > p.version:
                continue

            raise RuntimeError('Unsupported state spotted -- "updated_at" and "version" fields mismatch internal logic')

        result = list(filtered_projects.values())

        names = {x.name for x in result}

        if len(result) != len(names):
            raise RuntimeError('Unsupported state spotted -- multiple active projects with the same name!')

        return result

    def record_project(self, project: Project) -> None:
        """:meth:`.ToDoStorageProto.record_project` implementation."""

        projects = self.load_projects()
        project_found = None
        for p in projects:
            if project.name == p.name and project.id != p.id:
                raise RuntimeError('Unable to add project with non-unique name!')
            elif project.id == p.id:
                project_found = p

        if project_found:
            p.updated_at = todo_models_now()
            p.version += 1

        self._project().record_project(project)

    def task_status(self, task_id_query: typing.Union[uuid.UUID, str]) -> TaskStatus:
        """:meth:`.ToDoStorageProto.task_status` implementation."""
        # TODO: there should be a better way to retreive a status!

        task = exact_one_task(self.load_tasks(), task_id_query, query_full_match=False)

        if task.state_id is not None:
            for i in self.load_states_history():
                if i.id == task.state_id:
                    return i.next_state

        raise RuntimeError(f"The database does not have a state for a task \"{str(task.id)[:8]}\"")

    @verify_value(new_status=lambda x: x != TaskStatus.skipped)
    def set_task_status(
        self,
        task_id_query: typing.Union[uuid.UUID, str],
        new_status: TaskStatus,
        comment: typing.Optional[str] = None,
    ) -> Task:
        """:meth:`.ToDoStorageProto.set_task_status` implementation."""

        task = exact_one_task(self.load_tasks(), task_id_query, query_full_match=False)

        if self.task_status(task.id) == TaskStatus.deleted:
            raise ValueError('Unable to update status of the deleted task')

        now = todo_models_now()

        if new_status == TaskStatus.deleted:
            task.deleted_at = now
        elif new_status == TaskStatus.done:
            task.completed_at = now
        elif task.completed_at:
            task.completed_at = None

        state_event = StateUpdatedEvent(
            task_id=task.id,
            next_state=TaskStatus(new_status),
            comment=comment or ""
        )

        self._history().record_history_event(state_event)

        task.state_id = state_event.id
        self.record_task(task)

        return task

    def set_task_recurrence(
        self,
        task_id_query: typing.Union[uuid.UUID, str],
        rule: typing.Optional[RecurrenceRule] = None
    ) -> Task:
        """:meth:`.ToDoStorageProto.set_task_recurrence` implementation."""

        task = exact_one_task(self.load_tasks(), task_id_query, query_full_match=False)

        if rule:
            self._recurrence_rules().record_recurrence_rule(rule)
            task.recurrence_rule_id = rule.id
        else:
            task.recurrence_rule_id = None

        self.record_task(task)
        return task

    def reinitialize_recurrency_states(self) -> None:
        # TODO: mostly for recurrences

        current_recurrences_task = [
            x for x in self.load_tasks() if x.deleted_at is None and x.recurrence_rule_id is not None
        ]
        current_task_ids = [x.id for x in current_recurrences_task]

        rules = {x.id: x for x in self.load_recurrence_rules()}

        now_dt = todo_models_now()

        latest_states: typing.Dict[uuid.UUID, StateUpdatedEvent] = dict()
        for h in self.load_states_history():
            if h.task_id in current_task_ids:
                latest_states[h.task_id] = h

        for task in (x for x in self.load_tasks() if x.deleted_at is None and x.recurrence_rule_id is not None):

            if task.recurrence_rule_id is None:
                # this is for linters only!
                raise RuntimeError('Logic error -- a task without recurrence rule spotted')

            rule = rules[task.recurrence_rule_id]

            if rule.until_date and rule.until_date < now_dt:
                continue

            prev_state = latest_states[task.id]

            next_dt = None
            if rule.schedule_type == RecurrenceScheduleType.cron:
                next_dt = self._next_cron_statest(task, rule, prev_state)
            elif rule.schedule_type == RecurrenceScheduleType.rrule:
                next_dt = self._next_rrules_statest(task, rule, prev_state)
            else:
                raise ValueError(f'Unknown recurrence type -- {rule.schedule_type}')

            if next_dt is not None and next_dt < now_dt:
                if prev_state.next_state in (TaskStatus.pending, TaskStatus.in_progress):

                    # TODO: remove this copy-paste and join with the set_task_status method.
                    #   As a public contract, there shouldn't be able to set the "skipped" status
                    #   with the "set_task_status" method

                    state_event = StateUpdatedEvent(
                        task_id=task.id,
                        next_state=TaskStatus.skipped,
                        comment='A task was not completted in time'
                    )

                    self.record_history_event(state_event)

                    task.state_id = state_event.id
                    self.record_task(task)

                self.set_task_status(
                    task.id,
                    TaskStatus.pending,
                    comment='The recurrence rule "{str(rule.id)[:8]}" triggered'
                )

    def _next_cron_statest(
            self, task: Task, rule: RecurrenceRule, previous_state: StateUpdatedEvent
    ) -> datetime.datetime:
        cron_schedule = CronSchedule.from_string(rule.schedule_expression)

        start_dt = previous_state.created_at

        cron_iter = cron_schedule.iterate(start_dt)
        next_run_dt = next(cron_iter)
        if next_run_dt == start_dt:
            next_run_dt = next(cron_iter)
        return next_run_dt

    def _next_rrules_statest(
        self, task: Task, rule: RecurrenceRule, previous_state: StateUpdatedEvent
    ) -> datetime.datetime:

        rrule = dateutil.rrule.rrulestr(rule.schedule_expression, dtstart=task.created_at)
        rrule_iter = rrule.xafter(task.created_at)
        result = next(rrule_iter)

        while result < previous_state.created_at:
            result = next(rrule_iter)

        return result
