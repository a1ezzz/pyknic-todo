# -*- coding: utf-8 -*-
# pyknic_todo/bellboy.py
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

# TODO: tests

"""BellBoy integration plugin and CLI command handler for pyknic-todo."""

import datetime
import typing
import uuid

import pydantic
import pydantic_settings

from pyknic.lib.uri import URI
from pyknic.lib.bellboy.app import register_bellboy_command, BellBoyCommandHandler
from pyknic.lib.fastapi.models.lobby import LobbyCommandResult, LobbyKeyValueFeedbackResult, LobbyStrFeedbackResult
from pyknic.lib.fastapi.models.lobby import LobbyTableFeedbackResult
from pyknic.lib.io.aio_wrapper import AsyncWrapper

from pyknic_todo.models import TaskPriority, TaskStatus, Task, RecurrenceScheduleType, RecurrenceRule, todo_models_now
from pyknic_todo.storage.storage import storage_factory
from pyknic_todo.storage.proto import ToDoStorageProto

from pyknic_todo.version import __version__

import pyknic_todo.storage.json  # noqa: F401, E402  # forces json-storage


__plugin_version__ = f'pyknic-todo:{__version__}'


def init_plugin() -> None:
    """Initialize this package as a pyknic plugin."""
    register_bellboy_command()(BellBoyToDoCommand)


class ToDoAddCommandModel(pydantic.BaseModel):
    """Add a new task to the storage."""

    title: str = pydantic.Field(
        description='Title or summary of the task.',
        validation_alias=pydantic.AliasChoices('t', 'title'),
    )
    project: typing.Optional[str] = pydantic.Field(
        default=None,
        description='Optional project name for grouping related tasks.',
    )
    description: str = pydantic.Field(
        default='',
        description='Detailed description of the task.',
    )
    priority: TaskPriority = pydantic.Field(
        default=TaskPriority.medium,
        description='Priority level of the task (low, medium, high, urgent).',
        validation_alias=pydantic.AliasChoices('p', 'priority'),
    )
    tags: typing.List[str] = pydantic.Field(
        default_factory=list,
        description='List of tags or labels categorizing the task.',
    )

    # due_date:  # TODO: uncomment and process it


class ToDoTaskSelectModel(pydantic_settings.CliMutuallyExclusiveGroup):
    """Mutually exclusive task selector by ID prefix or exact title."""

    id: typing.Optional[str] = pydantic.Field(
        default=None,
        description='Unique task identifier or prefix of the UUID.',
    )
    title: typing.Optional[str] = pydantic.Field(
        default=None,
        description='Exact title of the task.',
    )


class ToDoDeleteCommandModel(pydantic.BaseModel):
    """Delete an existing task."""

    task: ToDoTaskSelectModel = pydantic.Field(
        description='Target task selector by ID prefix or title.',
    )


class ToDoDoneCommandModel(pydantic.BaseModel):
    """Mark a task as completed."""

    task: ToDoTaskSelectModel = pydantic.Field(
        description='Target task selector by ID prefix or title.',
    )
    comment: str = pydantic.Field(
        default='',
        description='Optional completion comment or note.',
    )


class ToDoStatusCommandModel(pydantic.BaseModel):
    """Change status of an existing task."""

    task: ToDoTaskSelectModel = pydantic.Field(
        description='Target task selector by ID prefix or title.',
    )
    status: TaskStatus = pydantic.Field(
        description='New task lifecycle status (pending, in_progress, done, cancelled, deleted).',
        validation_alias=pydantic.AliasChoices('s', 'status')
    )
    comment: str = pydantic.Field(
        default='',
        description='Optional comment explaining the status change.',
    )


class ToDoListCommandModel(pydantic.BaseModel):
    """List and filter tasks."""

    id: typing.Optional[str] = pydantic.Field(
        default=None,
        description='Filter tasks by UUID or UUID prefix.',
    )
    title: typing.Optional[str] = pydantic.Field(
        default=None,
        description='Filter tasks by exact title match.',
    )
    project: typing.Optional[typing.List[str]] = pydantic.Field(
        default=None,
        description='Filter tasks belonging to one of the specified projects.',
    )
    priority: typing.Optional[typing.List[TaskPriority]] = pydantic.Field(
        default=None,
        description='Filter tasks matching one of the specified priorities.',
    )
    tags: typing.Optional[typing.List[str]] = pydantic.Field(
        default=None,
        description='Filter tasks that share at least one of the specified tags.',
    )
    active_tasks: pydantic_settings.CliImplicitFlag[bool] = pydantic.Field(
        default=False,
        description='Filter tasks and include only those that are in progress or are pending',
        validation_alias=pydantic.AliasChoices('active-tasks')
    )
    completed_tasks: pydantic_settings.CliImplicitFlag[bool] = pydantic.Field(
        default=False,
        description='Filter tasks and include only those that are cancelled, skipped or are done',
        validation_alias=pydantic.AliasChoices('completed-tasks')
    )
    deleted_tasks: pydantic_settings.CliImplicitFlag[bool] = pydantic.Field(
        default=False,
        description='Filter tasks and include deleted tasks',
        validation_alias=pydantic.AliasChoices('deleted-tasks')
    )
    max_age: typing.Optional[int] = pydantic.Field(
        default=None,
        description='Filter tasks an include only those that has been changed in the last N days',
        validation_alias=pydantic.AliasChoices('max-age')
    )


class ToDoRepeatCommandModel(pydantic.BaseModel):
    """Set a recurrence schedule for a task."""

    task: ToDoTaskSelectModel = pydantic.Field(
        description='Target task selector by ID prefix or title.',
    )
    schedule_type: RecurrenceScheduleType = pydantic.Field(
        description='Recurrence schedule format (cron or rrule).',
        validation_alias=pydantic.AliasChoices('schedule-type'),
    )
    schedule: str = pydantic.Field(
        description='Schedule expression (e.g. cron string "0 9 * * 1" or RFC 5545 RRULE "FREQ=DAILY").',
    )
    until: typing.Optional[datetime.datetime] = pydantic.Field(
        default=None,
        description='Optional expiration date and time for the recurrence schedule.',
    )


class ToDoShowCommandModel(pydantic.BaseModel):
    """Show detailed information about a single task."""

    task: ToDoTaskSelectModel = pydantic.Field(
        description='Target task selector by ID prefix or title.',
    )


class ToDoHistoryCommandModel(pydantic.BaseModel):
    """Show status history of a single task."""

    task: ToDoTaskSelectModel = pydantic.Field(
        description='Target task selector by ID prefix or title.',
    )
    depth: int = pydantic.Field(
        default=10,
        ge=0,
        description='Depth of task status history to display.',
        validation_alias=pydantic.AliasChoices('depth', 'history-depth', 'd'),
    )


class ToDoCommandModel(pydantic.BaseModel):
    """Root command model for pyknic-todo BellBoy operations."""

    storage_uri: str = pydantic.Field(
        description='URI of the task storage backend (e.g. json+file:///path/to/storage).',
        validation_alias=pydantic.AliasChoices('storage-uri'),
    )
    add: pydantic_settings.CliSubCommand[ToDoAddCommandModel]
    delete: pydantic_settings.CliSubCommand[ToDoDeleteCommandModel]
    status: pydantic_settings.CliSubCommand[ToDoStatusCommandModel]
    done: pydantic_settings.CliSubCommand[ToDoDoneCommandModel]
    list: pydantic_settings.CliSubCommand[ToDoListCommandModel]
    repeat: pydantic_settings.CliSubCommand[ToDoRepeatCommandModel]
    show: pydantic_settings.CliSubCommand[ToDoShowCommandModel]
    history: pydantic_settings.CliSubCommand[ToDoHistoryCommandModel]


class BellBoyToDoCommand(BellBoyCommandHandler):
    """BellBoy command handler implementation for todo management operations."""

    def __init__(self, args: pydantic.BaseModel):
        """Initialize the todo command handler with validated arguments.

        :param args: Parsed command arguments instance.
        """
        BellBoyCommandHandler.__init__(self, args)

    @classmethod
    def command_name(cls) -> str:
        """The :meth:`.BellBoyCommandHandler.command_name` method implementation."""
        return 'todo'

    @classmethod
    def command_model(cls) -> typing.Type[pydantic.BaseModel]:
        """The :meth:`.BellBoyCommandHandler.command_model` method implementation."""
        return ToDoCommandModel

    async def exec(self) -> LobbyCommandResult:
        """Execute the requested subcommand asynchronously and return the result.

        :return: Command execution result containing feedback string or table data.
        :raises ValueError: If an unknown or unhandled subcommand is received.
        """
        assert(isinstance(self._args, ToDoCommandModel))

        caller = None

        if self._args.add:
            caller = await AsyncWrapper.create(self.__add)
        elif self._args.delete:
            caller = await AsyncWrapper.create(self.__delete)
        elif self._args.status:
            caller = await AsyncWrapper.create(self.__status)
        elif self._args.done:
            caller = await AsyncWrapper.create(self.__done)
        elif self._args.list:
            caller = await AsyncWrapper.create(self.__list)
        elif self._args.repeat:
            caller = await AsyncWrapper.create(self.__repeat)
        elif self._args.show:
            caller = await AsyncWrapper.create(self.__show)
        elif self._args.history:
            caller = await AsyncWrapper.create(self.__history)

        if caller is None:
            raise ValueError('Unknown subcommand spotted!')

        return await caller()  # type: ignore[no-any-return]

    def __storage(self) -> ToDoStorageProto:
        """Initialize and return a storage backend instance from the storage URI argument.

        :return: ToDo storage instance implementing ToDoStorageProto.
        """
        assert(isinstance(self._args, ToDoCommandModel))

        storage_uri = URI.parse(self._args.storage_uri)
        return storage_factory(storage_uri)

    def __add(self) -> LobbyCommandResult:
        """Execute the 'add' subcommand to create and persist a new task.

        :return: Feedback result indicating task creation.
        """
        assert(isinstance(self._args, ToDoCommandModel))
        assert(self._args.add)

        storage = self.__storage()
        task = Task(
            title=self._args.add.title,
            project=self._args.add.project,
            description=self._args.add.description,
            priority=self._args.add.priority,
            tags=self._args.add.tags
        )

        storage.append_task(task)
        return LobbyStrFeedbackResult(
            str_result=f'A new task was created -- {task.title} (id: {task.id}, '
            f'status: {storage.task_status(task.id)})',
            plugin_version=__plugin_version__
        )

    def __select_single_task(self, task_selector: ToDoTaskSelectModel) -> Task:
        """Find a single task matching the given selector by ID prefix or exact title.

        :param task_selector: Task selector criteria (ID prefix or title).
        :return: Matched Task entity.
        :raises ValueError: If no matching task is found or if multiple tasks match.
        """
        storage = self.__storage()

        task = None
        for t in storage.load_tasks():
            task_matched = False

            if task_selector.id and str(t.id).startswith(task_selector.id):
                task_matched = True

            if not task_matched and task_selector.title and t.title == task_selector.title:
                task_matched = True

            if not task_matched:
                continue

            if task is None:
                task = t
                continue

            raise ValueError('Multiple tasks spotted!')

        if task is None:
            raise ValueError('Unable to find a matching task')

        return task

    def __delete(self) -> LobbyCommandResult:
        """Execute the 'delete' subcommand to mark a task as deleted.

        :return: Feedback result indicating task deletion.
        """
        assert(isinstance(self._args, ToDoCommandModel))
        assert(self._args.delete)

        task = self.__select_single_task(self._args.delete.task)
        storage = self.__storage()
        storage.set_task_status(task.id, TaskStatus.deleted)

        return LobbyStrFeedbackResult(
            str_result=f'A task "{task.title}" (id: {task.id}) was deleted',
            plugin_version=__plugin_version__
        )

    def __status(self) -> LobbyCommandResult:
        """Execute the 'status' subcommand to update the status of a task.

        :return: Feedback result indicating task status update.
        """
        assert(isinstance(self._args, ToDoCommandModel))
        assert(self._args.status)

        task = self.__select_single_task(self._args.status.task)
        storage = self.__storage()
        storage.set_task_status(task.id, self._args.status.status, comment=self._args.status.comment)

        return LobbyStrFeedbackResult(
            str_result=f'A task "{task.title}" (id: {task.id}) was updated to {storage.task_status(task.id)}',
            plugin_version=__plugin_version__
        )

    def __done(self) -> LobbyCommandResult:
        """Execute the 'done' subcommand to mark a task as completed.

        :return: Feedback result indicating task completion.
        """
        assert(isinstance(self._args, ToDoCommandModel))
        assert(self._args.done)

        task = self.__select_single_task(self._args.done.task)
        storage = self.__storage()
        storage.set_task_status(task.id, TaskStatus.done, comment=self._args.done.comment)

        return LobbyStrFeedbackResult(
            str_result=f'A task "{task.title}" (id: {task.id}) was completed',
            plugin_version=__plugin_version__
        )

    def __list(self) -> LobbyCommandResult:
        """Execute the 'list' subcommand to filter and display tasks in tabular format.

        :return: Table feedback result containing matching tasks.
        """
        assert(isinstance(self._args, ToDoCommandModel))
        assert(self._args.list)

        storage = self.__storage()

        original_tasks = storage.load_tasks()

        print(f'Task add act comp -- {self._args.list.active_tasks}')

        tasks = []
        tasks_statuses: typing.Dict[uuid.UUID, TaskStatus] = dict()
        td_now = todo_models_now()
        td_filter: typing.Optional[datetime.datetime] = None
        if self._args.list.max_age:
            td_filter = (td_now - datetime.timedelta(days=self._args.list.max_age))

        if self._args.list.active_tasks or self._args.list.completed_tasks or self._args.list.deleted_tasks or any((
            self._args.list.id,
            self._args.list.title,
            self._args.list.project,
            self._args.list.priority,
            self._args.list.tags,
            td_filter
        )):
            for t in original_tasks:

                if self._args.list.id and not str(t.id).startswith(self._args.list.id):
                    continue

                if self._args.list.title and not t.title == self._args.list.title:
                    continue

                if self._args.list.project and t.project not in self._args.list.project:
                    continue

                if self._args.list.priority and t.priority not in self._args.list.priority:
                    continue

                if self._args.list.tags and t.tags and not (set(self._args.list.tags).intersection(t.tags)):
                    continue

                if td_filter and td_filter > t.updated_at:
                    continue

                task_status = storage.task_status(t.id)

                is_active = task_status in (TaskStatus.pending, TaskStatus.in_progress)
                is_completed = task_status in (TaskStatus.done, TaskStatus.cancelled, TaskStatus.skipped)
                is_deleted = (task_status == TaskStatus.deleted)

                if any((
                    self._args.list.active_tasks,
                    self._args.list.completed_tasks,
                    self._args.list.deleted_tasks
                )) and not any((
                    self._args.list.active_tasks and is_active,
                    self._args.list.completed_tasks and is_completed,
                    self._args.list.deleted_tasks and is_deleted,
                )):
                    continue

                tasks_statuses[t.id] = task_status
                tasks.append(t)

        else:
            tasks = original_tasks

        if tasks and not tasks_statuses:
            for t in tasks:
                tasks_statuses[t.id] = storage.task_status(t.id)

        return LobbyTableFeedbackResult(
            plugin_version=__plugin_version__,
            table_result={
                'title': [x.title for x in tasks],
                'id': [x.id for x in tasks],
                'project': [x.project for x in tasks],
                'priority': [x.priority.value for x in tasks],
                'status': [str(tasks_statuses[x.id].value) for x in tasks]
            }
        )

    def __repeat(self) -> LobbyCommandResult:
        """Execute the 'repeat' subcommand to attach a recurrence rule to a task.

        :return: Feedback result indicating recurrence rule configuration.
        """
        assert(isinstance(self._args, ToDoCommandModel))
        assert(self._args.repeat)

        task = self.__select_single_task(self._args.repeat.task)

        repeat_rule = RecurrenceRule(
            schedule_type=self._args.repeat.schedule_type,
            schedule_expression=self._args.repeat.schedule,
            until_date=self._args.repeat.until
        )

        storage = self.__storage()
        storage.set_task_recurrence(task.id, repeat_rule)

        return LobbyStrFeedbackResult(
            str_result=f'A repeat rule was set for a task "{task.title}" (id: {task.id})',
            plugin_version=__plugin_version__
        )

    def __show(self) -> LobbyCommandResult:
        """Execute the 'show' subcommand to display detailed information about a single task.

        :return: Key-value feedback result containing task details.
        """
        assert(isinstance(self._args, ToDoCommandModel))
        assert(self._args.show)

        task = self.__select_single_task(self._args.show.task)
        storage = self.__storage()

        recurrence_info = None
        if task.recurrence_rule_id:
            for rule in storage.load_recurrence_rules():
                if rule.id == task.recurrence_rule_id:
                    recurrence_info = f'{rule.schedule_type.value}: {rule.schedule_expression}'
                    if rule.until_date:
                        recurrence_info += f' (until {rule.until_date.isoformat()})'
                    break

        kv_result: typing.Dict[str, typing.Any] = {
            'id': str(task.id),
            'title': task.title,
            'status': storage.task_status(task.id).value,
            'priority': task.priority.value,
            'project': task.project,
            'description': task.description,
            'tags': task.tags,
            'due_date': task.due_date.isoformat() if task.due_date else None,
            'recurrence': recurrence_info,
            'version': task.version,
            'created_at': (
                task.created_at.isoformat() if isinstance(task.created_at, datetime.datetime) else str(task.created_at)
            ),
            'updated_at': (
                task.updated_at.isoformat() if isinstance(task.updated_at, datetime.datetime) else str(task.updated_at)
            ),
            'completed_at': task.completed_at.isoformat() if task.completed_at else None,
            'deleted_at': task.deleted_at.isoformat() if task.deleted_at else None,
            'storage_origin': str(task.storage_origin) if task.storage_origin else None,
        }

        return LobbyKeyValueFeedbackResult(
            plugin_version=__plugin_version__,
            kv_result=kv_result,
        )

    def __history(self) -> LobbyCommandResult:
        """Execute the 'history' subcommand to display status history for a single task.

        :return: Table feedback result containing status history events.
        """
        assert(isinstance(self._args, ToDoCommandModel))
        assert(self._args.history)

        task = self.__select_single_task(self._args.history.task)
        storage = self.__storage()

        all_history = storage.load_history()
        task_events = [e for e in all_history if e.task_id == task.id]
        task_events.sort(key=lambda e: e.created_at)

        depth = self._args.history.depth
        if depth > 0:
            selected_events = task_events[-depth:]
        else:
            selected_events = []

        return LobbyTableFeedbackResult(
            plugin_version=__plugin_version__,
            table_result={
                'status': [e.next_state.value for e in selected_events],
                'created_at': [e.created_at.isoformat() for e in selected_events],
                'comment': [e.comment for e in selected_events],
            }
        )
