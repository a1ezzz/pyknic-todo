# -*- coding: utf-8 -*-
# pyknic_todo/subcommands/show_cmd.py
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

import pydantic

from pyknic.lib.fastapi.models.lobby import LobbyCommandResult, LobbyKeyValueFeedbackResult

from pyknic_todo.storage.proto import ToDoStorageProto


from .general_models import ToDoSingleTaskSelectModel
from .common import select_single_task, __plugin_version__


class ToDoShowCommandModel(pydantic.BaseModel):
    """Show detailed information about a single task."""

    task: ToDoSingleTaskSelectModel = pydantic.Field(
        description='Target task selector by ID prefix or title.',
    )


def show_task(storage: ToDoStorageProto, args: typing.Optional[ToDoShowCommandModel]) -> LobbyCommandResult:
    """Execute the 'show' subcommand to display detailed information about a single task.

    :param storage: A storage to list tasks from
    :param args: task searching settings

    :return: Key-value feedback result containing task details.
    """

    if args is None:
        raise ValueError('Required arguments was not found')

    task = select_single_task(storage, args.task)

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
