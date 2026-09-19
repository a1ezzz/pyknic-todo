# -*- coding: utf-8 -*-
# pyknic_todo/models.py
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

# TODO: add docs!

import datetime
import enum
import typing
import uuid

import pydantic


def todo_models_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


@enum.unique
class TaskPriority(enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


@enum.unique
class TaskStatus(enum.Enum):
    new = "new"
    pending = "pending"
    in_progress = "in_progress"
    done = "done"
    cancelled = "cancelled"
    expired = "expired"
    skipped = "skipped"
    deleted = "deleted"


@enum.unique
class RecurrenceScheduleType(enum.Enum):
    rrule = "rrule"
    cron = "cron"


@enum.unique
class EndCondtionType(enum.Enum):
    never = "never"
    until_date = "until_date"
    count = "count"


class ToDoStorageSettings(pydantic.BaseModel):
    id: uuid.UUID = pydantic.Field(default_factory=uuid.uuid4)
    comment: str = ""


class EndCondition(pydantic.BaseModel):

    model_config = pydantic.ConfigDict(validate_assignment=True, extra='forbid', val_temporal_unit='seconds')

    condition_type: EndCondtionType = pydantic.Field(default=EndCondtionType.never)
    until_date: typing.Optional[datetime.datetime] = None
    max_occurrences: typing.Optional[int] = None


class RecurrenceRule(pydantic.BaseModel):

    model_config = pydantic.ConfigDict(
        validate_assignment=True, extra='forbid', frozen=True, val_temporal_unit='seconds'
    )

    id: uuid.UUID = pydantic.Field(default_factory=uuid.uuid4)
    schedule_type: RecurrenceScheduleType
    schedule_expression: str
    end_condition: EndCondition = pydantic.Field(default_factory=lambda: EndCondition())
    created_at: datetime.datetime = pydantic.Field(default_factory=todo_models_now)


class Task(pydantic.BaseModel):

    model_config = pydantic.ConfigDict(validate_assignment=True, extra='forbid', val_temporal_unit='seconds')

    id: uuid.UUID = pydantic.Field(default_factory=uuid.uuid4)
    title: str
    project: typing.Optional[str] = None
    description: typing.Annotated[str, pydantic.StringConstraints(strip_whitespace=True)] = ""
    priority: TaskPriority = pydantic.Field(default=TaskPriority.medium)
    due_date: typing.Optional[str] = None
    tags: list[str] = pydantic.Field(default_factory=list)
    recurrence_rule_id: typing.Optional[uuid.UUID] = None
    version: int = 1
    created_at: datetime.datetime = pydantic.Field(default_factory=todo_models_now)
    updated_at: datetime.datetime = pydantic.Field(default_factory=todo_models_now)
    completed_at: typing.Optional[datetime.datetime] = None
    deleted_at: typing.Optional[datetime.datetime] = None
    storage_origin: typing.Optional[uuid.UUID] = None


class StateUpdatedEvent(pydantic.BaseModel):

    model_config = pydantic.ConfigDict(validate_assignment=True, extra='forbid', val_temporal_unit='seconds')

    id: uuid.UUID = pydantic.Field(default_factory=uuid.uuid4)
    task_id: uuid.UUID
    created_at: datetime.datetime = pydantic.Field(default_factory=todo_models_now)
    next_state: TaskStatus
    comment: str = ""
    storage_origin: typing.Optional[uuid.UUID] = None
