"""Data models validated with Pydantic."""

# TODO: refactor this
# TODO: add client_id somewhere! (it should be persistent somehow)

from __future__ import annotations

import enum
import uuid

from datetime import datetime, timezone

from typing import Optional, Annotated
from pydantic import BaseModel, Field, ConfigDict, StringConstraints


def todo_models_now() -> datetime:
    return datetime.now(timezone.utc)


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
class RecurrenceEndCondtionType(enum.Enum):
    never = "never"
    until_date = "until_date"
    count = "count"


class ToDoStorageSettings(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    comment: str = ""


class EndCondition(BaseModel):

    # TODO: rename!

    model_config = ConfigDict(validate_assignment=True, extra='forbid', val_temporal_unit='seconds')

    condition_type: RecurrenceEndCondtionType = Field(default=RecurrenceEndCondtionType.never)
    until_date: Optional[datetime] = None
    max_occurrences: Optional[int] = None


class RecurrenceRule(BaseModel):
    # TODO: rename!

    model_config = ConfigDict(validate_assignment=True, extra='forbid', frozen=True, val_temporal_unit='seconds')

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    schedule_type: RecurrenceScheduleType
    schedule_expression: str
    end_condition: EndCondition = Field(default_factory=lambda: EndCondition())
    created_at: datetime = Field(default_factory=todo_models_now)


class Task(BaseModel):

    # TODO: rename this class

    model_config = ConfigDict(validate_assignment=True, extra='forbid', val_temporal_unit='seconds')

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    title: str
    project: Optional[str] = None
    description: Annotated[str, StringConstraints(strip_whitespace=True)] = ""
    priority: TaskPriority = Field(default=TaskPriority.medium)
    due_date: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    recurrence_rule_id: Optional[uuid.UUID] = None
    version: int = 1
    created_at: datetime = Field(default_factory=todo_models_now)
    updated_at: datetime = Field(default_factory=todo_models_now)
    completed_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    storage_origin: Optional[uuid.UUID] = None


class StateHistoryEvent(BaseModel):
    # TODO: rename this class

    model_config = ConfigDict(validate_assignment=True, extra='forbid', val_temporal_unit='seconds')

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    task_id: uuid.UUID
    created_at: datetime = Field(default_factory=todo_models_now)
    next_state: TaskStatus
    comment: str = ""
    storage_origin: Optional[uuid.UUID] = None
