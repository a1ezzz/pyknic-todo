# -*- coding: utf-8 -*-
# pyknic_todo/subcommands/general_models.py
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

from pyknic_todo.models import TaskPriority


class ToDoSingleTaskSelectModel(pydantic_settings.CliMutuallyExclusiveGroup):
    """Mutually exclusive a single task selector by ID prefix or exact title."""

    id: typing.Optional[str] = pydantic.Field(
        default=None,
        description='Unique task identifier or prefix of the UUID.',
    )
    title: typing.Optional[str] = pydantic.Field(
        default=None,
        description='Exact title of the task.',
    )


class ToDoTasksListSelectModel(pydantic_settings.CliMutuallyExclusiveGroup):
    """A tasks list selector by ID prefix or exact title."""

    id: typing.Optional[typing.List[str]] = pydantic.Field(
        default=None,
        description='Tasks identifiers or prefix of UUIDs.',
    )
    title: typing.Optional[typing.List[str]] = pydantic.Field(
        default=None,
        description='Exact titles of tasks.',
    )


class ToDoTaskSelectorCommandModel(pydantic.BaseModel):
    """General tasks selector model"""

    priority: typing.Optional[typing.List[TaskPriority]] = pydantic.Field(
        default=None,
        description='Filter tasks matching one of the specified priorities.',
    )

    tags: typing.Optional[typing.List[str]] = pydantic.Field(
        default=None,
        description='Filter tasks that share at least one of the specified tags.',
    )

    active_tasks: pydantic_settings.CliImplicitFlag[bool] = pydantic.Field(
        default=True,
        description='Filter tasks and include only those that are in progress or are pending',
        validation_alias=pydantic.AliasChoices('active-tasks')
    )

    completed_tasks: pydantic_settings.CliImplicitFlag[bool] = pydantic.Field(
        default=False,
        description='Filter tasks and include only those that are cancelled, skipped or are done',
        validation_alias=pydantic.AliasChoices('completed-tasks')
    )

    deleted_tasks: pydantic_settings.CliImplicitFlag[bool] = pydantic.Field(
        default=False,
        description='Filter tasks and include deleted tasks',
        validation_alias=pydantic.AliasChoices('deleted-tasks')
    )

    max_age: typing.Optional[int] = pydantic.Field(
        default=None,
        description='Filter tasks an include only those that has been changed in the last N days',
        validation_alias=pydantic.AliasChoices('max-age')
    )


class ToDoUpsertCommandModel(pydantic.BaseModel):
    """Add a new task to the storage."""

    title: str = pydantic.Field(
        description='Title or summary of the task.',
        validation_alias=pydantic.AliasChoices('t', 'title'),
    )
    project: typing.Optional[str] = pydantic.Field(
        default=None,
        description='Optional project name for grouping related tasks.',
    )
    description: str = pydantic.Field(
        default='',
        description='Detailed description of the task.',
    )
    priority: TaskPriority = pydantic.Field(
        default=TaskPriority.medium,
        description='Priority level of the task (low, medium, high, urgent).',
        validation_alias=pydantic.AliasChoices('p', 'priority'),
    )
    tags: typing.List[str] = pydantic.Field(
        default_factory=list,
        description='List of tags or labels categorizing the task.',
    )

    # due_date:  # TODO: uncomment and process it
