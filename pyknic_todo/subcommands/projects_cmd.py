# -*- coding: utf-8 -*-
# pyknic_todo/subcommands/projects_cmd.py
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

from pyknic_todo.storage.proto import ToDoStorageProto
from pyknic_todo.models import todo_models_now, TaskStatus

from .common import __plugin_version__
from .general_models import ToDoTaskSelectorCommandModel


class ToDoProjectsCommandModel(ToDoTaskSelectorCommandModel):
    """List known projects
    """

    include_empty: pydantic_settings.CliImplicitFlag[bool] = pydantic.Field(
        default=False,
        description='Whether to include projects without tasks',
        validation_alias=pydantic.AliasChoices('include-empty')
    )


def list_projects(storage: ToDoStorageProto, args: typing.Optional[ToDoProjectsCommandModel]) -> LobbyCommandResult:
    """Execute the 'projects' subcommand to list all the projects

    :param storage: A storage to search projects from
    :param args: projects searching settings

    :return: Feedback result indicating task deletion.
    """

    if args is None:
        raise ValueError('Required arguments was not found')

    projects = storage.load_projects()
    tasks = storage.load_tasks()

    include_projects: typing.List[uuid.UUID] = list()
    processed_projects: typing.List[uuid.UUID] = list()
    tasks_count: typing.Dict[uuid.UUID, int] = dict()

    td_filter: typing.Optional[datetime.datetime] = None
    if args.max_age:
        td_filter = (todo_models_now() - datetime.timedelta(days=args.max_age))

    for t in tasks:
        # TODO: this is a common logic with the 'list' command

        if t.project_id is None:
            continue

        processed_projects.append(t.project_id)

        if args.priority and t.priority not in args.priority:
            continue

        if args.tags and not t.tags and not (set(args.tags).intersection(t.tags)):
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

        include_projects.append(t.project_id)

    for t in tasks:

        if t.project_id is None:
            continue

        if t.project_id in include_projects:
            count = tasks_count.get(t.project_id, 0)
            count += 1
            tasks_count[t.project_id] = count

    if args.include_empty:
        for p in projects:
            if p.id not in tasks_count and p.id not in processed_projects:
                tasks_count[p.id] = 0
                include_projects.append(p.id)

    filtered_projects = [x for x in projects if x.id in include_projects]

    return LobbyTableFeedbackResult(
        table_result={
            'project': [x.name for x in filtered_projects],
            'description': [x.description for x in filtered_projects],
            'tasks count': [tasks_count[x.id] for x in filtered_projects]
        },
        plugin_version=__plugin_version__
    )
