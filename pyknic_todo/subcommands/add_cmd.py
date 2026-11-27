# -*- coding: utf-8 -*-
# pyknic_todo/subcommands/add_cmd.py
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

import typing

import pydantic

from pyknic.lib.fastapi.models.lobby import LobbyCommandResult, LobbyStrFeedbackResult

from pyknic_todo.models import Task, Project
from pyknic_todo.storage.proto import ToDoStorageProto

from .common import __plugin_version__, select_single_project_by_name
from .general_models import ToDoUpsertGeneralFieldsModel


class ToDoAddCommandModel(ToDoUpsertGeneralFieldsModel):
    """Add a new task to the storage."""

    title: str = pydantic.Field(
        description='Title or summary of the task.',
        validation_alias=pydantic.AliasChoices('t', 'title'),
    )


def add_task(storage: ToDoStorageProto, args: typing.Optional[ToDoAddCommandModel]) -> LobbyCommandResult:
    """Execute the 'add' subcommand to create and persist a new task.

    :param storage: A storage to add a task to
    :param args: a new task settings

    :return: Feedback result indicating task creation.
    """

    if args is None:
        raise ValueError('Required arguments was not found')

    project_id = None
    if args.project is not None:
        project = select_single_project_by_name(storage, args.project)
        if project is None:
            project = Project(name=args.project)
            storage.record_project(project)
        project_id = project.id

    task = Task(
        title=args.title,
        project_id=project_id,
        description=args.description,
        priority=args.priority,
        tags=args.tags
    )

    storage.record_task(task)

    return LobbyStrFeedbackResult(
        str_result=f'A new task was created -- {task.title} (id: {task.id}, '
        f'status: {storage.task_status(task.id)})',
        plugin_version=__plugin_version__
    )
