# -*- coding: utf-8 -*-
# pyknic_todo/subcommands/list_cmd.py
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

import datetime
import typing
import uuid

import pydantic
import pydantic_settings

from pyknic.lib.fastapi.models.lobby import LobbyCommandResult, LobbyTableFeedbackResult

from pyknic_todo.models import TaskPriority, TaskStatus, todo_models_now
from pyknic_todo.storage.proto import ToDoStorageProto

from .common import __plugin_version__


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
    full_id: pydantic_settings.CliImplicitFlag[bool] = pydantic.Field(
        default=False,
        description='Display full UUID instead of the first 8 characters.',
        validation_alias=pydantic.AliasChoices('full-id')
    )


def list_tasks(storage: ToDoStorageProto, args: typing.Optional[ToDoListCommandModel]) -> LobbyCommandResult:
    """Execute the 'list' subcommand to filter and display tasks in tabular format.

    :param storage: A storage to list tasks from
    :param args: tasks filtering settings

    :return: Table feedback result containing matching tasks.
    """

    if args is None:
        raise ValueError('Required arguments was not found')

    original_tasks = storage.load_tasks()

    tasks = []
    tasks_statuses: typing.Dict[uuid.UUID, TaskStatus] = dict()
    td_now = todo_models_now()
    td_filter: typing.Optional[datetime.datetime] = None
    if args.max_age:
        td_filter = (td_now - datetime.timedelta(days=args.max_age))

    if args.active_tasks or args.completed_tasks or args.deleted_tasks or any((
        args.id,
        args.title,
        args.project,
        args.priority,
        args.tags,
        td_filter
    )):
        for t in original_tasks:

            if args.id and not str(t.id).startswith(args.id):
                continue

            if args.title and not t.title == args.title:
                continue

            if args.project and t.project not in args.project:
                continue

            if args.priority and t.priority not in args.priority:
                continue

            if args.tags and t.tags and not (set(args.tags).intersection(t.tags)):
                continue

            if td_filter and td_filter > t.updated_at:
                continue

            task_status = storage.task_status(t.id)

            is_active = task_status in (TaskStatus.pending, TaskStatus.in_progress)
            is_completed = task_status in (TaskStatus.done, TaskStatus.cancelled, TaskStatus.skipped)
            is_deleted = (task_status == TaskStatus.deleted)

            if any((
                args.active_tasks,
                args.completed_tasks,
                args.deleted_tasks
            )) and not any((
                args.active_tasks and is_active,
                args.completed_tasks and is_completed,
                args.deleted_tasks and is_deleted,
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
            'id': [str(x.id) if args.full_id else str(x.id)[:8] for x in tasks],
            'project': [x.project for x in tasks],
            'priority': [x.priority.value for x in tasks],
            'status': [str(tasks_statuses[x.id].value) for x in tasks],
            'repeating': [x.recurrence_rule_id is not None for x in tasks],
        }
    )
