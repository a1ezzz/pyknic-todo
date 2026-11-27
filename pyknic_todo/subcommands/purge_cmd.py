# -*- coding: utf-8 -*-
# pyknic_todo/subcommands/purge_cmd.py
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
import pydantic_settings

from pyknic.lib.fastapi.models.lobby import LobbyCommandResult, LobbyStrFeedbackResult

from pyknic_todo.storage.proto import ToDoStorageProto

from .common import __plugin_version__


class ToDoPurgeCommandModel(pydantic.BaseModel):
    """Cleanup the storage."""
    # TODO: this command must have more options, especially when a synchronization command will
    #   be implemented

    remove_deleted: pydantic_settings.CliImplicitFlag[bool] = pydantic.Field(
        default=True,
        description='Whether to remove deleted tasks',
        validation_alias=pydantic.AliasChoices('remove-deleted')
    )

    remove_completed: pydantic_settings.CliImplicitFlag[bool] = pydantic.Field(
        default=False,
        description='Whether to remove completed tasks',
        validation_alias=pydantic.AliasChoices('remove-completed')
    )

    reduce_history: pydantic_settings.CliImplicitFlag[bool] = pydantic.Field(
        default=False,
        description='Whether to reduce history',
        validation_alias=pydantic.AliasChoices('reduce-history')
    )

    remove_empty_projects: pydantic_settings.CliImplicitFlag[bool] = pydantic.Field(
        default=False,
        description='Whether to remove projects without tasks',
        validation_alias=pydantic.AliasChoices('remove-empty-projects')
    )


def purge_task(storage: ToDoStorageProto, args: typing.Optional[ToDoPurgeCommandModel]) -> LobbyCommandResult:
    """Execute the 'purge' subcommand to cleanup a storage

    :param storage: A storage to clean
    :param args: a will be arguments
    """

    if args is None:
        raise ValueError('Required arguments was not found')

    removed_rows = storage.purge_data(
        remove_deleted_task=args.remove_deleted,
        remove_completed_task=args.remove_completed,
        reduce_history=args.reduce_history,
        remove_empty_projects=args.remove_empty_projects
    )

    return LobbyStrFeedbackResult(
        str_result=f'The storage has been cleaned; {removed_rows} rows have been removed.',
        plugin_version=__plugin_version__
    )
