# -*- coding: utf-8 -*-
# pyknic_todo/bellboy.py
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

"""BellBoy integration plugin and CLI command handler for pyknic-todo."""

import functools
import pathlib
import typing

import pydantic
import pydantic_settings

from pyknic.lib.config import Config
from pyknic.lib.uri import URI
from pyknic.lib.bellboy.app import register_bellboy_command, BellBoyCommandHandler
from pyknic.lib.fastapi.models.lobby import LobbyCommandResult
from pyknic.lib.io.aio_wrapper import AsyncWrapper

from pyknic_todo.storage.storage import storage_factory
from pyknic_todo.storage.proto import ToDoStorageProto
from pyknic_todo.path import root_path

import pyknic_todo.storage.json  # noqa: F401, E402  # forces json-storage

from pyknic_todo.subcommands.add_cmd import ToDoAddCommandModel, add_task
from pyknic_todo.subcommands.delete_cmd import ToDoDeleteCommandModel, delete_tasks
from pyknic_todo.subcommands.done_cmd import ToDoDoneCommandModel, done_tasks
from pyknic_todo.subcommands.history_cmd import ToDoHistoryCommandModel, task_history
from pyknic_todo.subcommands.list_cmd import ToDoListCommandModel, list_tasks
from pyknic_todo.subcommands.projects_cmd import ToDoProjectsCommandModel, list_projects
from pyknic_todo.subcommands.repeat_cmd import ToDoRepeatCommandModel, repeat_task
from pyknic_todo.subcommands.show_cmd import ToDoShowCommandModel, show_task
from pyknic_todo.subcommands.status_cmd import ToDoStatusCommandModel, tasks_status


def init_plugin() -> None:
    """Initialize this package as a pyknic plugin."""
    register_bellboy_command()(BellBoyToDoCommand)


class ToDoCommandModel(pydantic.BaseModel):
    """Root command model for pyknic-todo BellBoy operations."""

    todo_config: str = pydantic.Field(
        description='Configuration file. By default, the one from a current working directory is used',
        validation_alias=pydantic.AliasChoices('todo-config'),
        default='./.pyknic-todo.yaml'
    )

    storage_uri: typing.Optional[str] = pydantic.Field(
        description='URI of the task storage backend (e.g. json+file:///path/to/storage).',
        validation_alias=pydantic.AliasChoices('storage-uri'),
        default=None
    )
    add: pydantic_settings.CliSubCommand[ToDoAddCommandModel]
    delete: pydantic_settings.CliSubCommand[ToDoDeleteCommandModel]
    status: pydantic_settings.CliSubCommand[ToDoStatusCommandModel]
    done: pydantic_settings.CliSubCommand[ToDoDoneCommandModel]
    list: pydantic_settings.CliSubCommand[ToDoListCommandModel]
    projects: pydantic_settings.CliSubCommand[ToDoProjectsCommandModel]
    repeat: pydantic_settings.CliSubCommand[ToDoRepeatCommandModel]
    show: pydantic_settings.CliSubCommand[ToDoShowCommandModel]
    history: pydantic_settings.CliSubCommand[ToDoHistoryCommandModel]


class BellBoyToDoCommand(BellBoyCommandHandler):
    """BellBoy command handler implementation for todo management operations."""

    def __init__(self, args: pydantic.BaseModel):
        """Initialize the todo command handler with validated arguments.

        :param args: Parsed command arguments instance.
        """
        BellBoyCommandHandler.__init__(self, args)

    @classmethod
    def command_name(cls) -> str:
        """The :meth:`.BellBoyCommandHandler.command_name` method implementation."""
        return 'todo'

    @classmethod
    def command_model(cls) -> typing.Type[pydantic.BaseModel]:
        """The :meth:`.BellBoyCommandHandler.command_model` method implementation."""
        return ToDoCommandModel

    async def exec(self) -> LobbyCommandResult:
        """Execute the requested subcommand asynchronously and return the result.

        :return: Command execution result containing feedback string or table data.
        :raises ValueError: If an unknown or unhandled subcommand is received.
        """

        if not isinstance(self._args, ToDoCommandModel):
            raise TypeError('Invalid command arguments type')

        caller = None

        if self._args.add:
            caller = await AsyncWrapper.create(functools.partial(add_task, self.__storage(), self._args.add))
        elif self._args.delete:
            caller = await AsyncWrapper.create(functools.partial(delete_tasks, self.__storage(), self._args.delete))
        elif self._args.status:
            caller = await AsyncWrapper.create(functools.partial(tasks_status, self.__storage(), self._args.status))
        elif self._args.done:
            caller = await AsyncWrapper.create(functools.partial(done_tasks, self.__storage(), self._args.done))
        elif self._args.list:
            caller = await AsyncWrapper.create(functools.partial(list_tasks, self.__storage(), self._args.list))
        elif self._args.projects:
            caller = await AsyncWrapper.create(functools.partial(list_projects, self.__storage(), self._args.projects))
        elif self._args.repeat:
            caller = await AsyncWrapper.create(functools.partial(repeat_task, self.__storage(), self._args.repeat))
        elif self._args.show:
            caller = await AsyncWrapper.create(functools.partial(show_task, self.__storage(), self._args.show))
        elif self._args.history:
            caller = await AsyncWrapper.create(functools.partial(task_history, self.__storage(), self._args.history))

        if caller is None:
            raise ValueError('Unknown subcommand spotted!')

        return await caller()  # type: ignore[no-any-return]

    def __config(self) -> Config:
        if not isinstance(self._args, ToDoCommandModel):
            raise TypeError('Invalid command arguments type')

        config = Config()
        with (root_path / 'default_config.yaml').open() as f:
            config.merge_file(f)

        if self._args.todo_config:
            config_file = pathlib.Path(self._args.todo_config)

            default_path = ToDoCommandModel.model_fields['todo_config'].get_default()
            if self._args.todo_config == default_path and not config_file.exists():
                return config

            with config_file.open() as f:
                config.merge_file(f)

        return config

    def __storage(self) -> ToDoStorageProto:
        """Initialize and return a storage backend instance from the storage URI argument.

        :return: ToDo storage instance implementing ToDoStorageProto.
        """
        if not isinstance(self._args, ToDoCommandModel):
            raise TypeError('Invalid command arguments type')

        config = self.__config()
        default_storage = config['storage-uri'].as_str() if not config['storage-uri'].is_none() else None
        storage_str = self._args.storage_uri or default_storage

        if storage_str is None:
            raise ValueError('Storage URI was not set! You should you a cli argument or a configuration file')

        storage_uri = URI.parse(storage_str)
        return storage_factory(storage_uri)
