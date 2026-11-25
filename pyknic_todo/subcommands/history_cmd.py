# -*- coding: utf-8 -*-
# pyknic_todo/subcommands/history_cmd.py
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

from pyknic.lib.fastapi.models.lobby import LobbyCommandResult, LobbyTableFeedbackResult

from pyknic_todo.storage.proto import ToDoStorageProto

from .general_models import ToDoSingleTaskSelectModel
from .common import __plugin_version__, select_single_task


class ToDoHistoryCommandModel(pydantic.BaseModel):
    """Show status history of a single task."""

    task: ToDoSingleTaskSelectModel = pydantic.Field(
        description='Target task selector by ID prefix or title.',
    )
    depth: int = pydantic.Field(
        default=10,
        ge=0,
        description='Depth of task status history to display.',
        validation_alias=pydantic.AliasChoices('depth', 'history-depth', 'd'),
    )


def task_history(storage: ToDoStorageProto, args: typing.Optional[ToDoHistoryCommandModel]) -> LobbyCommandResult:
    """Execute the 'history' subcommand to display status history for a single task.

    :param storage: A storage to update tasks from
    :param args: tasks searching settings

    :return: Table feedback result containing status history events.
    """

    if args is None:
        raise ValueError('Required arguments was not found')

    task = select_single_task(storage, args.task)

    all_history = storage.load_states_history()
    task_events = [e for e in all_history if e.task_id == task.id]
    task_events.sort(key=lambda e: e.created_at)

    depth = args.depth
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
