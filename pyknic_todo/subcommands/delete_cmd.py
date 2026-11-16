# -*- coding: utf-8 -*-
# pyknic_todo/subcommands/delete_cmd.py
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

from pyknic_todo.models import TaskStatus
from pyknic_todo.storage.proto import ToDoStorageProto

from .common import __plugin_version__, select_multiple_tasks
from .general_models import ToDoTasksListSelectModel


class ToDoDeleteCommandModel(pydantic.BaseModel):
    """Delete an existing task."""

    task: ToDoTasksListSelectModel = pydantic.Field(
        description='Target task selector by ID prefix or title.',
    )


def delete_tasks(storage: ToDoStorageProto, args: typing.Optional[ToDoDeleteCommandModel]) -> LobbyCommandResult:
    """Execute the 'delete' subcommand to mark a task as deleted.

    :param storage: A storage to delete tasks from
    :param args: tasks searching settings

    :return: Feedback result indicating task deletion.
    """

    if args is None:
        raise ValueError('Required arguments was not found')

    tasks = select_multiple_tasks(storage, args.task)
    for t in tasks:
        storage.set_task_status(t.id, TaskStatus.deleted)

    if len(tasks) == 1:
        return LobbyStrFeedbackResult(
            str_result=f'A task "{tasks[0].title}" (id: {tasks[0].id}) was deleted',
            plugin_version=__plugin_version__
        )

    return LobbyStrFeedbackResult(
        str_result=f'{len(tasks)} tasks were deleted',
        plugin_version=__plugin_version__
    )
