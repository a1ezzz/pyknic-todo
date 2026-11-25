# -*- coding: utf-8 -*-
# pyknic_todo/subcommands/update_cmd.py
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

from pyknic_todo.storage.proto import ToDoStorageProto

from .common import __plugin_version__, select_single_task
from .general_models import ToDoUpsertCommandModel, ToDoSingleTaskSelectModel


class ToDoUpdateCommandModel(ToDoUpsertCommandModel):
    """Update a task in the storage."""

    task: ToDoSingleTaskSelectModel = pydantic.Field(
        description='Target task selector by ID prefix or title.',
    )


def update_task(storage: ToDoStorageProto, args: typing.Optional[ToDoUpdateCommandModel]) -> LobbyCommandResult:
    """Execute the 'update' subcommand to update a task.

    :param storage: A storage to update a task from
    :param args: a new task settings

    :return: Feedback result indicating task creation.
    """

    if args is None:
        raise ValueError('Required arguments was not found')

    task = select_single_task(storage, args.task)

    if args.title:
        task.title = args.title

    if args.project:
        task.project = args.project

    if args.description:
        task.description = args.description

    if args.priority:
        task.priority = args.priority

    if args.tags:
        task.tags = args.tags

    storage.record_task(task)

    return LobbyStrFeedbackResult(
        str_result=f'A task was updated -- {task.title} (id: {task.id}, '
        f'status: {storage.task_status(task.id)})',
        plugin_version=__plugin_version__
    )
