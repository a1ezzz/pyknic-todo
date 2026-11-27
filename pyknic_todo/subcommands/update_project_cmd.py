# -*- coding: utf-8 -*-
# pyknic_todo/subcommands/update_project_cmd.py
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
from pyknic_todo.models import Project

from .common import select_single_project_by_name, __plugin_version__


class ToDoUpdateProjectCommandModel(pydantic.BaseModel):
    """Update project name and/or description."""

    project: str = pydantic.Field(
        description='A project name to update.',
    )

    name: typing.Optional[str] = pydantic.Field(
        default=None,
        description='A new name of the project.',
    )

    description: typing.Optional[str] = pydantic.Field(
        default=None,
        description='Detailed description of the project.',
    )


def update_project(
    storage: ToDoStorageProto, args: typing.Optional[ToDoUpdateProjectCommandModel]
) -> LobbyCommandResult:
    """Execute the 'update-project' subcommand to update the projects

    :param storage: A storage to update projects from
    :param args: new project properties

    :return: Feedback result indicating project update
    """

    if args is None:
        raise ValueError('Required arguments was not found')

    project = select_single_project_by_name(storage, args.project)
    if project is None:
        project = Project(name=(args.name or args.project), description=args.description)
    else:
        if args.name:
            project.name = args.name
        if args.description is not None:
            project.description = args.description

    storage.record_project(project)

    return LobbyStrFeedbackResult(
        str_result=f'A project was updated -- {project.name} (id: {project.id})',
        plugin_version=__plugin_version__
    )
