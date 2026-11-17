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

import typing

from pyknic.lib.fastapi.models.lobby import LobbyCommandResult, LobbyTableFeedbackResult, LobbyListValueFeedbackResult

from pyknic_todo.storage.proto import ToDoStorageProto

from .common import __plugin_version__
from .general_models import ToDoTaskSelectorCommandModel
from .list_cmd import list_tasks, ToDoListCommandModel


class ToDoProjectsCommandModel(ToDoTaskSelectorCommandModel):
    pass


def list_projects(storage: ToDoStorageProto, args: typing.Optional[ToDoProjectsCommandModel]) -> LobbyCommandResult:
    """Execute the 'projects' subcommand to list all the projects

    :param storage: A storage to search projects from
    :param args: projects searching settings

    :return: Feedback result indicating task deletion.
    """

    if args is None:
        raise ValueError('Required arguments was not found')

    tasks_list = list_tasks(
        storage,
        ToDoListCommandModel(
            priority=args.priority,
            tags=args.tags,
            active_tasks=args.active_tasks,
            completed_tasks=args.completed_tasks,
            deleted_tasks=args.deleted_tasks,
            max_age=args.max_age
        )
    )

    if not isinstance(tasks_list, LobbyTableFeedbackResult):
        raise TypeError('Invalid function result. The "LobbyTableFeedbackResult" class is expected')

    projects = {x for x in tasks_list.table_result['project'] if x is not None}
    sorted_projects = list(projects)
    sorted_projects.sort()

    return LobbyListValueFeedbackResult(
        list_result=sorted_projects,
        plugin_version=__plugin_version__
    )
