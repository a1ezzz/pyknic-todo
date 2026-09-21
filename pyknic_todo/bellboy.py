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
# TODO: docs
# TODO: descriptions!

import datetime
import typing

import pydantic
import pydantic_settings

from pyknic.lib.uri import URI
from pyknic.lib.bellboy.app import register_bellboy_command, BellBoyCommandHandler
from pyknic.lib.fastapi.models.lobby import LobbyCommandResult, LobbyStrFeedbackResult, LobbyTableFeedbackResult
from pyknic.lib.io.aio_wrapper import AsyncWrapper

from pyknic_todo.models import TaskPriority, TaskStatus, Task, RecurrenceScheduleType, RecurrenceRule
from pyknic_todo.storage.storage import storage_factory
from pyknic_todo.storage.proto import ToDoStorageProto

from pyknic_todo.version import __version__

import pyknic_todo.storage.json  # noqa: F401, E402  # forces json-storage


__plugin_version__ = f'pyknic-todo:{__version__}'


def init_plugin() -> None:
    register_bellboy_command()(BellBoyToDoCommand)


class ToDoAddCommandModel(pydantic.BaseModel):
    title: str = pydantic.Field(description='!!!', validation_alias=pydantic.AliasChoices('t', 'title'))
    project: typing.Optional[str] = None
    description: str = ""
    priority: TaskPriority = pydantic.Field(
        description='!!!', default=TaskPriority.medium, validation_alias=pydantic.AliasChoices('p', 'priority')
    )
    tags: typing.List[str] = pydantic.Field(default_factory=list, description='!!!')

    # due_date:  # TODO: uncomment and process it


class ToDoTaskSelectModel(pydantic_settings.CliMutuallyExclusiveGroup):
    id: typing.Optional[str] = pydantic.Field(description='!!!', default=None)
    title: typing.Optional[str] = pydantic.Field(description='!!!', default=None)


class ToDoDeleteCommandModel(pydantic.BaseModel):
    task: ToDoTaskSelectModel


class ToDoDoneCommandModel(pydantic.BaseModel):
    task: ToDoTaskSelectModel
    comment: str = pydantic.Field(description='!!!', default='')


class ToDoStatusCommandModel(pydantic.BaseModel):
    task: ToDoTaskSelectModel
    status: TaskStatus = pydantic.Field(description='!!!', validation_alias=pydantic.AliasChoices('s', 'status'))
    comment: str = pydantic.Field(description='!!!', default='')


class ToDoListCommandModel(pydantic.BaseModel):
    id: typing.Optional[str] = pydantic.Field(description='!!!', default=None)
    title: typing.Optional[str] = pydantic.Field(description='!!!', default=None)
    project: typing.Optional[typing.List[str]] = pydantic.Field(description='!!!', default=None)
    priority: typing.Optional[typing.List[TaskPriority]] = pydantic.Field(description='!!!', default=None)
    tags: typing.Optional[typing.List[TaskPriority]] = pydantic.Field(description='!!!', default=None)

    # TODO: add custom meta-modes like: 'active' (default), 'all', or 'completed' or 'new'/in_progress


class ToDoRepeatCommandModel(pydantic.BaseModel):
    task: ToDoTaskSelectModel

    schedule_type: RecurrenceScheduleType = pydantic.Field(
        description='!!!', validation_alias=pydantic.AliasChoices('schedule-type')
    )
    schedule: str = pydantic.Field(description='!!!')
    until: typing.Optional[datetime.datetime] = pydantic.Field(description='!!!', default=None)


class ToDoCommandModel(pydantic.BaseModel):

    storage_uri: str = pydantic.Field(
        description='files location', validation_alias=pydantic.AliasChoices('storage-uri')
    )
    add: pydantic_settings.CliSubCommand[ToDoAddCommandModel]
    delete: pydantic_settings.CliSubCommand[ToDoDeleteCommandModel]
    status: pydantic_settings.CliSubCommand[ToDoStatusCommandModel]
    done: pydantic_settings.CliSubCommand[ToDoDoneCommandModel]
    list: pydantic_settings.CliSubCommand[ToDoListCommandModel]
    repeat: pydantic_settings.CliSubCommand[ToDoRepeatCommandModel]
    # TODO: add command for detailed view of a single task


class BellBoyToDoCommand(BellBoyCommandHandler):

    def __init__(self, args: pydantic.BaseModel):
        BellBoyCommandHandler.__init__(self, args)

    @classmethod
    def command_name(cls) -> str:
        """ The :meth:`.BellBoyCommandHandler.command_name` method implementation
        """
        return 'todo'

    @classmethod
    def command_model(cls) -> typing.Type[pydantic.BaseModel]:
        """ The :meth:`.BellBoyCommandHandler.command_model` method implementation
        """
        return ToDoCommandModel

    async def exec(self) -> LobbyCommandResult:
        assert(isinstance(self._args, ToDoCommandModel))

        caller = None

        if self._args.add:
            caller = await AsyncWrapper.create(self.__add)
        elif self._args.delete:
            caller = await AsyncWrapper.create(self.__delete)
        elif self._args.status:
            caller = await AsyncWrapper.create(self.__status)
        elif self._args.done:
            caller = await AsyncWrapper.create(self.__done)
        elif self._args.list:
            caller = await AsyncWrapper.create(self.__list)
        elif self._args.repeat:
            caller = await AsyncWrapper.create(self.__repeat)

        if caller is None:
            raise ValueError('Unknown subcommand spotted!')

        return await caller()  # type: ignore[no-any-return]

    def __storage(self) -> ToDoStorageProto:
        assert(isinstance(self._args, ToDoCommandModel))

        storage_uri = URI.parse(self._args.storage_uri)
        return storage_factory(storage_uri)

    def __add(self) -> LobbyCommandResult:
        assert(isinstance(self._args, ToDoCommandModel))
        assert(self._args.add)

        storage = self.__storage()
        task = Task(
            title=self._args.add.title,
            project=self._args.add.project,
            description=self._args.add.description,
            priority=self._args.add.priority,
            tags=self._args.add.tags
        )

        storage.append_task(task)
        return LobbyStrFeedbackResult(
            str_result=f'A new task was created -- {task.title} (id: {task.id}, '
            f'status: {storage.task_status(task.id)})',
            plugin_version=__plugin_version__
        )

    def __select_single_task(self, task_selector: ToDoTaskSelectModel) -> Task:
        storage = self.__storage()

        task = None
        for t in storage.load_tasks():
            task_matched = False

            if task_selector.id and str(t.id).startswith(task_selector.id):
                task_matched = True

            if not task_matched and task_selector.title and t.title == task_selector.title:
                task_matched = True

            if not task_matched:
                continue

            if task is None:
                task = t
                continue

            raise ValueError('Multiple tasks spotted!')

        if task is None:
            raise ValueError('Unable to find a matching task')

        return task

    def __delete(self) -> LobbyCommandResult:
        assert(isinstance(self._args, ToDoCommandModel))
        assert(self._args.delete)

        task = self.__select_single_task(self._args.delete.task)
        storage = self.__storage()
        storage.set_task_status(task.id, TaskStatus.deleted)

        return LobbyStrFeedbackResult(
            str_result=f'A task "{task.title}" (id: {task.id}) was deleted',
            plugin_version=__plugin_version__
        )

    def __status(self) -> LobbyCommandResult:
        assert(isinstance(self._args, ToDoCommandModel))
        assert(self._args.status)

        task = self.__select_single_task(self._args.status.task)
        storage = self.__storage()
        storage.set_task_status(task.id, self._args.status.status, comment=self._args.status.comment)

        return LobbyStrFeedbackResult(
            str_result=f'A task "{task.title}" (id: {task.id}) was updated to {storage.task_status(task.id)}',
            plugin_version=__plugin_version__
        )

    def __done(self) -> LobbyCommandResult:
        assert(isinstance(self._args, ToDoCommandModel))
        assert(self._args.done)

        task = self.__select_single_task(self._args.done.task)
        storage = self.__storage()
        storage.set_task_status(task.id, TaskStatus.done, comment=self._args.done.comment)

        return LobbyStrFeedbackResult(
            str_result=f'A task "{task.title}" (id: {task.id}) was completed',
            plugin_version=__plugin_version__
        )

    def __list(self) -> LobbyCommandResult:
        assert(isinstance(self._args, ToDoCommandModel))
        assert(self._args.list)

        storage = self.__storage()

        original_tasks = storage.load_tasks()

        tasks = []

        if any((
            self._args.list.id,
            self._args.list.title,
            self._args.list.project,
            self._args.list.priority,
            self._args.list.tags
        )):
            for t in original_tasks:

                if self._args.list.id and str(t.id).startswith(self._args.list.id):
                    tasks.append(t)

                if self._args.list.title and t.title == self._args.list.title:
                    tasks.append(t)

                if self._args.list.project and t.project in self._args.list.project:
                    tasks.append(t)

                if self._args.list.priority and t.priority in self._args.list.priority:
                    tasks.append(t)

                if self._args.list.tags and t.tags and set(self._args.list.tags).intersection(t.tags):
                    tasks.append(t)
        else:
            tasks = original_tasks

        return LobbyTableFeedbackResult(
            plugin_version=__plugin_version__,
            table_result={
                'title': [x.title for x in tasks],
                'id': [x.id for x in tasks],
                'project': [x.project for x in tasks],
                'priority': [x.priority.value for x in tasks],
                'status': [str(storage.task_status(x.id).value) for x in tasks]
            }
        )

    def __repeat(self) -> LobbyCommandResult:
        assert(isinstance(self._args, ToDoCommandModel))
        assert(self._args.repeat)

        task = self.__select_single_task(self._args.repeat.task)

        repeat_rule = RecurrenceRule(
            schedule_type=self._args.repeat.schedule_type,
            schedule_expression=self._args.repeat.schedule,
            until_date=self._args.repeat.until
        )

        storage = self.__storage()
        storage.set_task_recurrence(task.id, repeat_rule)

        return LobbyStrFeedbackResult(
            str_result=f'A repeat rule was set for a task "{task.title}" (id: {task.id})',
            plugin_version=__plugin_version__
        )
