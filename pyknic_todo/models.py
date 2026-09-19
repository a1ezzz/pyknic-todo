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

# TODO: check docs

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
    """Priority levels for a task.

    Members:
        low: Low priority task.
        medium: Normal / medium priority task (default).
        high: High priority task.
        urgent: Urgent priority task requiring immediate attention.
    """

    # Low priority task
    low = "low"
    # Normal / medium priority task (default)
    medium = "medium"
    # High priority task
    high = "high"
    # Urgent priority task requiring immediate attention
    urgent = "urgent"


@enum.unique
class TaskStatus(enum.Enum):
    """Lifecycle status states for tasks.

    Members:
        new: Newly scheduled task for future execution.
        pending: Task is ready for execution.
        in_progress: Task is actively being worked on.
        done: Task has been completed.
        cancelled: Task was cancelled and will not be executed.
        expired: Task passed its deadline without being completed.
        skipped: Recurring task occurrence was skipped.
        deleted: Task was marked as deleted (soft delete).
    """

    # Newly scheduled task for future execution
    new = "new"
    # Task is ready for execution
    pending = "pending"
    # Task is actively being worked on
    in_progress = "in_progress"
    # Task has been completed
    done = "done"
    # Task was cancelled and will not be executed
    cancelled = "cancelled"
    # Task passed its deadline without being completed
    expired = "expired"
    # Recurring task occurrence was skipped
    skipped = "skipped"
    # Task was marked as deleted (soft delete)
    deleted = "deleted"


@enum.unique
class RecurrenceScheduleType(enum.Enum):
    """Supported schedule expression formats for recurring tasks.

    Members:
        rrule: RFC 5545 iCalendar recurrence rule (e.g., 'FREQ=WEEKLY;BYDAY=MO,WE,FR').
        cron: Standard cron format schedule expression (e.g., '0 10 * * 1-5').
    """

    # RFC 5545 iCalendar recurrence rule (e.g., 'FREQ=WEEKLY;BYDAY=MO,WE,FR')
    rrule = "rrule"
    # Standard cron format schedule expression (e.g., '0 10 * * 1-5')
    cron = "cron"


@enum.unique
class EndCondtionType(enum.Enum):
    """Types of termination conditions for recurring task schedules.

    Members:
        never: Task repeats indefinitely.
        until_date: Task repetition stops after a specified date and time.
        count: Task repetition stops after reaching a maximum number of occurrences.
    """

    # Task repeats indefinitely
    never = "never"
    # Task repetition stops after a specified date and time
    until_date = "until_date"
    # Task repetition stops after reaching a maximum number of occurrences
    count = "count"


class ToDoStorageSettings(pydantic.BaseModel):
    """Storage-level configuration and metadata.

    Attributes:
        id: Unique identifier for the storage instance (acts as origin/client ID).
        comment: Optional human-readable comment or description for this storage.
    """

    # Unique identifier for the storage instance
    id: uuid.UUID = pydantic.Field(
        default_factory=uuid.uuid4,
        description="Unique identifier for the storage instance.",
    )
    # Optional human-readable comment or description for this storage
    comment: str = pydantic.Field(
        default="",
        description="Optional human-readable comment or description for this storage.",
    )


class EndCondition(pydantic.BaseModel):
    """Condition determining when a recurrence rule terminates.

    Attributes:
        condition_type: Type of termination condition (never, until_date, or count).
        until_date: Optional cutoff datetime after which no more tasks are scheduled.
        max_occurrences: Optional upper bound on the number of task occurrences.
    """

    model_config = pydantic.ConfigDict(validate_assignment=True, extra='forbid', val_temporal_unit='seconds')

    # Type of termination condition (never, until_date, count)
    condition_type: EndCondtionType = pydantic.Field(
        default=EndCondtionType.never,
        description="Type of termination condition (never, until_date, or count).",
    )
    # Optional cutoff datetime after which no more tasks are scheduled
    until_date: typing.Optional[datetime.datetime] = pydantic.Field(
        default=None,
        description="Optional cutoff datetime after which no more tasks are scheduled.",
    )
    # Optional upper bound on the total number of task occurrences
    max_occurrences: typing.Optional[int] = pydantic.Field(
        default=None,
        description="Optional upper bound on the total number of task occurrences.",
    )


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

    # Unique identifier of the recurrence rule
    id: uuid.UUID = pydantic.Field(
        default_factory=uuid.uuid4,
        description="Unique identifier of the recurrence rule.",
    )
    # Format of the schedule expression (rrule or cron)
    schedule_type: RecurrenceScheduleType = pydantic.Field(
        description="Format of the schedule expression (rrule or cron).",
    )
    # Schedule pattern string (RFC 5545 RRULE or cron expression)
    schedule_expression: str = pydantic.Field(
        description="Schedule pattern string (RFC 5545 RRULE or cron expression).",
    )
    # Termination criteria specifying when repetition ceases
    end_condition: EndCondition = pydantic.Field(
        default_factory=lambda: EndCondition(),
        description="Termination criteria specifying when repetition ceases.",
    )
    # Creation timestamp of the recurrence rule in UTC
    created_at: datetime.datetime = pydantic.Field(
        default_factory=todo_models_now,
        description="Creation timestamp of the recurrence rule in UTC.",
    )


class Task(pydantic.BaseModel):
    """Representation of an individual todo task item.

    Attributes:
        id: Unique identifier of the task (UUID).
        title: Short summary or title of the task.
        project: Optional project or list name grouping related tasks.
        description: Detailed task description with Markdown support (whitespace stripped).
        priority: Priority level assigned to the task (defaults to medium).
        due_date: Optional due date / deadline string.
        tags: List of tags or labels categorizing the task.
        recurrence_rule_id: Optional UUID reference to a linked recurrence rule.
        version: Optimistic locking version counter for sync and concurrency control.
        created_at: Initial creation timestamp in UTC.
        updated_at: Last modification timestamp in UTC.
        completed_at: Completion timestamp in UTC (set when task is done).
        deleted_at: Deletion timestamp in UTC for soft-deleted tasks.
        storage_origin: UUID of the storage or client that created or last modified the task.
    """

    model_config = pydantic.ConfigDict(validate_assignment=True, extra='forbid', val_temporal_unit='seconds')

    # Unique identifier of the task
    id: uuid.UUID = pydantic.Field(
        default_factory=uuid.uuid4,
        description="Unique identifier of the task.",
    )
    # Short summary or title of the task
    title: str = pydantic.Field(
        description="Short summary or title of the task.",
    )
    # Optional project or list name grouping related tasks
    project: typing.Optional[str] = pydantic.Field(
        default=None,
        description="Optional project or list name grouping related tasks.",
    )
    # Detailed task description with Markdown support (whitespace stripped)
    description: typing.Annotated[str, pydantic.StringConstraints(strip_whitespace=True)] = pydantic.Field(
        default="",
        description="Detailed task description with Markdown support.",
    )
    # Priority level assigned to the task
    priority: TaskPriority = pydantic.Field(
        default=TaskPriority.medium,
        description="Priority level assigned to the task.",
    )
    # Optional due date / deadline string
    due_date: typing.Optional[str] = pydantic.Field(
        default=None,
        description="Optional due date / deadline string.",
    )
    # List of tags or labels categorizing the task
    tags: list[str] = pydantic.Field(
        default_factory=list,
        description="List of tags or labels categorizing the task.",
    )
    # Optional UUID reference to a linked recurrence rule for recurring tasks
    recurrence_rule_id: typing.Optional[uuid.UUID] = pydantic.Field(
        default=None,
        description="Optional UUID reference to a linked recurrence rule for recurring tasks.",
    )
    # Optimistic locking version counter for sync and concurrency control
    version: int = pydantic.Field(
        default=1,
        description="Optimistic locking version counter for sync and concurrency control.",
    )
    # Initial creation timestamp in UTC
    created_at: datetime.datetime = pydantic.Field(
        default_factory=todo_models_now,
        description="Initial creation timestamp in UTC.",
    )
    # Last modification timestamp in UTC
    updated_at: datetime.datetime = pydantic.Field(
        default_factory=todo_models_now,
        description="Last modification timestamp in UTC.",
    )
    # Completion timestamp in UTC (set when task is done)
    completed_at: typing.Optional[datetime.datetime] = pydantic.Field(
        default=None,
        description="Completion timestamp in UTC (set when task is done).",
    )
    # Deletion timestamp in UTC for soft-deleted tasks
    deleted_at: typing.Optional[datetime.datetime] = pydantic.Field(
        default=None,
        description="Deletion timestamp in UTC for soft-deleted tasks.",
    )
    # UUID of the storage or client that created or last modified the task
    storage_origin: typing.Optional[uuid.UUID] = pydantic.Field(
        default=None,
        description="UUID of the storage or client that created or last modified the task.",
    )


class StateUpdatedEvent(pydantic.BaseModel):
    """Audit log event recording a task state transition.

    Attributes:
        id: Unique identifier of this event.
        task_id: UUID of the task whose state changed.
        created_at: Timestamp when the state transition occurred in UTC.
        next_state: New status the task transitioned into.
        comment: Optional explanatory comment or reason for the state change.
        storage_origin: UUID of the storage or client that recorded the event.
    """

    model_config = pydantic.ConfigDict(validate_assignment=True, extra='forbid', val_temporal_unit='seconds')

    # Unique identifier of this event
    id: uuid.UUID = pydantic.Field(
        default_factory=uuid.uuid4,
        description="Unique identifier of this event.",
    )
    # UUID of the task whose state changed
    task_id: uuid.UUID = pydantic.Field(
        description="UUID of the task whose state changed.",
    )
    # Timestamp when the state transition occurred in UTC
    created_at: datetime.datetime = pydantic.Field(
        default_factory=todo_models_now,
        description="Timestamp when the state transition occurred in UTC.",
    )
    # New status the task transitioned into
    next_state: TaskStatus = pydantic.Field(
        description="New status the task transitioned into.",
    )
    # Optional explanatory comment or reason for the state change
    comment: str = pydantic.Field(
        default="",
        description="Optional explanatory comment or reason for the state change.",
    )
    # UUID of the storage or client that recorded the event
    storage_origin: typing.Optional[uuid.UUID] = pydantic.Field(
        default=None,
        description="UUID of the storage or client that recorded the event.",
    )
