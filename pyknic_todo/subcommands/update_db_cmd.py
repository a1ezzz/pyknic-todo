# -*- coding: utf-8 -*-
# pyknic_todo/subcommands/update_db_cmd.py
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
from pyknic.lib.uri import URI
from pyknic_todo.storage.proto import ToDoStorageProto
from pyknic_todo.storage.registry import __storage_registry__

from .common import __plugin_version__


class ToDoUpdateDBCommandModel(pydantic.BaseModel):
    """Update the storage scheme."""
    pass


def update_db(storage_uri: URI, args: typing.Optional[ToDoUpdateDBCommandModel]) -> LobbyCommandResult:
    """Execute the 'update-db' subcommand to update a storage scheme

    :param storage: A storage to update
    :param args: a dummy argument (is not used at the moment)

    :return: Feedback result indicating DB update.
    """

    if args is None:
        raise ValueError('Required arguments was not found')

    storage_handler_cls: typing.Type[ToDoStorageProto] = __storage_registry__.get(storage_uri.scheme)

    next_version = storage_handler_cls.update_scheme(storage_uri)

    # sanity check, that migration completed successfully
    _ = storage_handler_cls.create_storage(storage_uri)

    return LobbyStrFeedbackResult(
        str_result=f'A database was updated to -- {next_version}',
        plugin_version=__plugin_version__
    )
