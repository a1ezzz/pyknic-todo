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
import types
import typing
import uuid

import dateutil.rrule

from pyknic.lib.tasks.scheduler.cron_source import CronSchedule
from pyknic.lib.verify import verify_value

from pyknic_todo.models import Task, TaskStatus, RecurrenceRule, StateUpdatedEvent, todo_models_now
from pyknic_todo.models import RecurrenceScheduleType

from .proto import ToDoStorageProto
from .helpers import partial_uuid_select


class TaskStorageUpdaterContextProto(metaclass=abc.ABCMeta):
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
        raise NotImplementedError('This method is abstract')


class PlainTaskStorageProto(metaclass=abc.ABCMeta):
    """Abstract interface for task storage backends."""

    @abc.abstractmethod
    def load_tasks(self) -> list[Task]:
        """Load all tasks."""
        raise NotImplementedError('This method is abstract')

    @abc.abstractmethod
    def save_tasks(self, tasks: list[Task]) -> None:
        """Replace tasks and save them.

        :param tasks: a new set of tasks (previous tasks will be discared)
        """
        raise NotImplementedError('This method is abstract')

    @abc.abstractmethod
    def updater_context(
        self, task_id_query: typing.Union[uuid.UUID, str], query_full_match: bool = True
    ) -> TaskStorageUpdaterContextProto:
        """Return a context that helps to update a single task that was found by the specified criteria

        :param task_id_query: a task identifier to update (a partial uuid submittion is supported)
        :param query_full_match: whether a task_id_query is a full identifier or a partial match may be used (work only
        if a task_id_query is str-object)
        """
        raise NotImplementedError('This method is abstract')

    @abc.abstractmethod
    def append_task(self, task: Task) -> None:
        """Append a new task in a storage.

        :param task: a new task to add
        """
        raise NotImplementedError('This method is abstract')


class PlainRecurrenceRuleStorageProto(metaclass=abc.ABCMeta):
    """Abstract interface for recurrence rule storage backends."""

    @abc.abstractmethod
    def load_recurrence_rules(self) -> list[RecurrenceRule]:
        """Load all recurrence rules."""
        raise NotImplementedError('This method is abstract')

    @abc.abstractmethod
    def save_recurrence_rules(self, rules: list[RecurrenceRule]) -> None:
        """Replace recurrence rules and save them.

        :param rules: a new set of rules (previous rules will be discared)
        """
        raise NotImplementedError('This method is abstract')

    @abc.abstractmethod
    def append_recurrence_rule(self, rule: RecurrenceRule) -> None:
        """Persist a new recurrence rule.

        :param rule: a new rule to add
        """
        raise NotImplementedError('This method is abstract')


class PlainStateHistoryStorageProto(metaclass=abc.ABCMeta):
    """Abstract interface for state history storage backends."""

    @abc.abstractmethod
    def load_history(self) -> list[StateUpdatedEvent]:
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

        return [e for e in self.load_history() if partial_uuid_select(e.task_id, task_id_query)]

    def task_latest_status(self, task_id_query: typing.Union[uuid.UUID, str]) -> TaskStatus:
        """Return the latest status for a task

        :param task_id_query: a task identifier to update (a partial uuid submittion is supported)
        """
        events = self.find_events_for_task(task_id_query)
        if events:
            return (events[-1].next_state)

        raise ValueError(f'Task id "{task_id_query}" was not found')


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

    def storage_id(self) -> uuid.UUID:
        """:meth:`.ToDoStorageProto.storage_id` implementation."""
        return self._settings().storage_id()

    def load_tasks(self) -> list[Task]:
        """:meth:`.ToDoStorageProto.load_tasks` implementation."""
        return self._tasks().load_tasks()

    def save_tasks(self, tasks: list[Task]) -> None:
        """:meth:`.ToDoStorageProto.save_tasks` implementation."""
        self._tasks().save_tasks(tasks)

    def load_recurrence_rules(self) -> list[RecurrenceRule]:
        """:meth:`.ToDoStorageProto.load_recurrence_rules` implementation."""
        return self._recurrence_rules().load_recurrence_rules()

    def save_recurrence_rules(self, rules: list[RecurrenceRule]) -> None:
        """:meth:`.ToDoStorageProto.save_recurrence_rules` implementation."""
        self._recurrence_rules().save_recurrence_rules(rules)

    def load_history(self) -> list[StateUpdatedEvent]:
        """:meth:`.ToDoStorageProto.load_history` implementation."""
        return self._history().load_history()

    def record_history_event(self, event: StateUpdatedEvent) -> None:
        """:meth:`.ToDoStorageProto.record_history_event` implementation."""
        self._history().record_history_event(event)

    def append_task(self, task: Task) -> None:
        """:meth:`.ToDoStorageProto.append_task` implementation."""

        self._tasks().append_task(task)

        self._history().record_history_event(
            StateUpdatedEvent(
                task_id=task.id,
                next_state=TaskStatus.pending,
            )
        )

    def task_status(self, task_id_query: typing.Union[uuid.UUID, str]) -> TaskStatus:
        """:meth:`.ToDoStorageProto.task_status` implementation."""
        # TODO: there should be a better way to retreive a status!

        with self._tasks().updater_context(task_id_query, query_full_match=False) as tc:
            return self._history().task_latest_status(tc().id)

    @verify_value(new_status=lambda x: x != TaskStatus.skipped)
    def set_task_status(
        self,
        task_id_query: typing.Union[uuid.UUID, str],
        new_status: TaskStatus,
        comment: typing.Optional[str] = None,
    ) -> Task:
        """:meth:`.ToDoStorageProto.set_task_status` implementation."""

        if new_status == TaskStatus.skipped:
            raise ValueError(f'Invalid state to set -- {TaskStatus.skipped}')

        with self._tasks().updater_context(task_id_query, query_full_match=False) as tc:
            task = tc()

            if self.task_status(task.id) == TaskStatus.deleted:
                raise ValueError('Unable to update status of the deleted task')

            now = todo_models_now()

            if new_status == TaskStatus.deleted:
                task.deleted_at = now
            elif new_status == TaskStatus.done:
                task.completed_at = now
            elif task.completed_at:
                task.completed_at = None

            task.updated_at = now
            task.version += 1
            tc.commit()

            self._history().record_history_event(
                StateUpdatedEvent(
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
        """:meth:`.ToDoStorageProto.set_task_recurrence` implementation."""

        with self._tasks().updater_context(task_id_query, query_full_match=False) as tc:
            task = tc()

            if rule:
                self._recurrence_rules().append_recurrence_rule(rule)
                task.recurrence_rule_id = rule.id
            else:
                task.recurrence_rule_id = None

            task.version += 1
            task.updated_at = todo_models_now()

            tc.commit()
            return task

    def reinitialize_recurrency_states(self) -> None:
        # TODO: mostly for recurrences

        current_recurrences_task = [
            x for x in self.load_tasks() if x.deleted_at is None and x.recurrence_rule_id is not None
        ]
        current_task_ids = [x.id for x in current_recurrences_task]

        rules = {x.id: x for x in self.load_recurrence_rules()}
        orphaned_rules = set(rules.keys())

        now_dt = todo_models_now()

        latest_states: typing.Dict[uuid.UUID, StateUpdatedEvent] = dict()
        for h in self.load_history():
            if h.task_id in current_task_ids:
                latest_states[h.task_id] = h

        for task in (x for x in self.load_tasks() if x.recurrence_rule_id):
            assert(task.recurrence_rule_id)

            orphaned_rules.remove(task.recurrence_rule_id)
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
                    skipped_event = StateUpdatedEvent(
                        task_id=task.id,
                        next_state=TaskStatus.skipped,
                        comment='A task was not completted in time'
                    )
                    self.record_history_event(skipped_event)

                self.record_history_event(StateUpdatedEvent(
                    task_id=task.id,
                    next_state=TaskStatus.pending,
                    comment=f'The recurrence rule "{str(rule.id)[:8]}" triggered'
                ))

        self.save_recurrence_rules([x for x in rules.values() if x.id not in orphaned_rules])

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

        assert(isinstance(result, datetime.datetime))
        return result
