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

"""Domain models and data structures for pyknic-todo.

This module defines core data types, enumeration classes, and Pydantic models
used throughout the pyknic-todo application for tasks, recurrence rules,
state change events, and storage settings.
"""

import datetime
import enum
import typing
import uuid

import pydantic


def todo_models_now() -> datetime.datetime:
    """Return the current datetime in UTC timezone."""
    return datetime.datetime.now(datetime.timezone.utc)


@enum.unique
class TaskPriority(enum.Enum):
    """Priority levels for a task."""

    low = "low"        # Low priority task
    medium = "medium"  # Normal / medium priority task (default)
    high = "high"      # High priority task
    urgent = "urgent"  # Urgent priority task requiring immediate attention


@enum.unique
class TaskStatus(enum.Enum):
    """Lifecycle status states for tasks."""

    pending = "pending"          # Task is ready for execution
    in_progress = "in_progress"  # Task is actively being worked on
    done = "done"                # Task has been completed
    cancelled = "cancelled"      # Task was cancelled and will not be executed
    skipped = "skipped"          # Recurring task occurrence was skipped
    deleted = "deleted"          # Task was marked as deleted (soft delete)


@enum.unique
class RecurrenceScheduleType(enum.Enum):
    """Supported schedule expression formats for recurring tasks."""

    rrule = "rrule"  # RFC 5545 iCalendar recurrence rule (e.g., 'FREQ=WEEKLY;BYDAY=MO,WE,FR')
    cron = "cron"  # Standard cron format schedule expression (e.g., '0 10 * * 1-5')


class ToDoStorageSettings(pydantic.BaseModel):
    """Storage-level configuration and metadata.

    Attributes:
        id: Unique identifier for the storage instance (acts as origin/client ID).
        comment: Optional human-readable comment or description for this storage.
    """

    id: uuid.UUID = pydantic.Field(default_factory=uuid.uuid4)
    comment: str = pydantic.Field(default="")


class RecurrenceRule(pydantic.BaseModel):
    """Repetition rule specification for recurring tasks.

    Attributes:
        id: Unique identifier of the recurrence rule.
        schedule_type: Format of the schedule expression (rrule or cron).
        schedule_expression: Schedule pattern string (RFC 5545 RRULE or cron expression).
        end_condition: Termination criteria specifying when repetition ceases.
        created_at: Creation timestamp of the recurrence rule in UTC.
    """

    model_config = pydantic.ConfigDict(
        validate_assignment=True, extra='forbid', frozen=True, val_temporal_unit='seconds'
    )

    id: uuid.UUID = pydantic.Field(default_factory=uuid.uuid4)
    schedule_type: RecurrenceScheduleType
    schedule_expression: str
    until_date: typing.Optional[datetime.datetime] = None
    created_at: datetime.datetime = pydantic.Field(default_factory=todo_models_now)


class Task(pydantic.BaseModel):
    """Representation of an individual todo task item.

    Attributes:
        id: Unique identifier of the task (UUID).
        title: Short summary or title of the task.
        project: Optional project for grouping related tasks.
        description: Detailed task description with Markdown support (whitespace stripped).
        priority: Priority level assigned to the task (defaults to medium).
        due_date: Optional due date / deadline string.
        tags: List of tags or labels categorizing the task.
        recurrence_rule_id: Optional UUID reference to a linked recurrence rule.
        version: Optimistic locking version counter for syncronization
        created_at: Initial creation timestamp in UTC.
        updated_at: Last modification timestamp in UTC.
        completed_at: Completion timestamp in UTC (set when task is done).
        deleted_at: Deletion timestamp in UTC for soft-deleted tasks.
        storage_origin: UUID of the storage that created or last modified the task.
    """

    model_config = pydantic.ConfigDict(validate_assignment=True, extra='forbid', val_temporal_unit='seconds')

    id: uuid.UUID = pydantic.Field(default_factory=uuid.uuid4)
    title: str
    project: typing.Optional[str] = None
    description: typing.Annotated[str, pydantic.StringConstraints(strip_whitespace=True)] = ""
    priority: TaskPriority = pydantic.Field(default=TaskPriority.medium)
    due_date: typing.Optional[datetime.datetime] = None
    tags: list[str] = pydantic.Field(default_factory=list)
    recurrence_rule_id: typing.Optional[uuid.UUID] = None
    version: int = pydantic.Field(default=1)
    created_at: datetime.datetime = pydantic.Field(default_factory=todo_models_now)
    updated_at: datetime.datetime = pydantic.Field(default_factory=todo_models_now)
    completed_at: typing.Optional[datetime.datetime] = None
    deleted_at: typing.Optional[datetime.datetime] = None
    storage_origin: typing.Optional[uuid.UUID] = None


class StateUpdatedEvent(pydantic.BaseModel):
    """History log event recording a task state transition.

    Attributes:
        id: Unique identifier of this event.
        task_id: UUID of the task whose state changed.
        created_at: Timestamp when the state transition occurred in UTC.
        next_state: New status the task transitioned into.
        comment: Optional explanatory comment or reason for the state change.
        storage_origin: UUID of the storage that recorded the event.
    """

    model_config = pydantic.ConfigDict(validate_assignment=True, extra='forbid', val_temporal_unit='seconds')

    id: uuid.UUID = pydantic.Field(default_factory=uuid.uuid4)
    task_id: uuid.UUID
    created_at: datetime.datetime = pydantic.Field(default_factory=todo_models_now)
    next_state: TaskStatus
    comment: str = pydantic.Field(default="")
    storage_origin: typing.Optional[uuid.UUID] = None
