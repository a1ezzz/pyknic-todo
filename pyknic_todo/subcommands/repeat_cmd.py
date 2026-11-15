# -*- coding: utf-8 -*-
# pyknic_todo/subcommands/repeat_cmd.py
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

from pyknic.lib.fastapi.models.lobby import LobbyCommandResult, LobbyStrFeedbackResult

from pyknic_todo.models import RecurrenceScheduleType, RecurrenceRule
from pyknic_todo.storage.proto import ToDoStorageProto

from .general_models import ToDoTasksListSelectModel
from .common import __plugin_version__, select_multiple_tasks


class ToDoRepeatCommandModel(pydantic.BaseModel):
    """Set a recurrence schedule for a task."""

    task: ToDoTasksListSelectModel = pydantic.Field(
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


def repeat_task(storage: ToDoStorageProto, args: typing.Optional[ToDoRepeatCommandModel]) -> LobbyCommandResult:
    """Execute the 'repeat' subcommand to attach a recurrence rule to a task.

    :param storage: A storage to list tasks from
    :param args: tasks filtering settings

    :return: Feedback result indicating recurrence rule configuration.
    """

    if args is None:
        raise ValueError('Required arguments was not found')

    repeat_rule = RecurrenceRule(
        schedule_type=args.schedule_type,
        schedule_expression=args.schedule,
        until_date=args.until
    )

    tasks = select_multiple_tasks(storage, args.task)
    for t in tasks:
        storage.set_task_recurrence(t.id, repeat_rule)

    if len(tasks) == 1:
        return LobbyStrFeedbackResult(
            str_result=f'A repeat rule was set for a task "{tasks[0].title}" (id: {tasks[0].id})',
            plugin_version=__plugin_version__
        )

    return LobbyStrFeedbackResult(
        str_result=f'{len(tasks)} tasks were updated (a repeating rule was set)',
        plugin_version=__plugin_version__
    )
