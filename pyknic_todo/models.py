"""Data models validated with Pydantic."""

from __future__ import annotations

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field

TaskStatus = Literal[
    "new",
    "pending",
    "in_progress",
    "done",
    "cancelled",
    "skipped",
    "deleted",
]

TaskPriority = Literal["low", "medium", "high", "urgent"]
ScheduleType = Literal["rrule", "cron"]
EndConditionType = Literal["never", "until_date", "count"]


class EndCondition(BaseModel):
    type: EndConditionType = "never"
    until_date: Optional[str] = None
    max_occurrences: Optional[int] = None


class RecurrenceRule(BaseModel):
    id: str
    schedule_type: ScheduleType
    schedule_expression: str
    end_condition: EndCondition
    created_at: str


class Task(BaseModel):
    id: str
    project_id: Optional[str] = None
    title: str
    description: str = ""
    status: TaskStatus = "pending"
    priority: TaskPriority = "medium"
    due_date: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    recurrence_rule_id: Optional[str] = None
    parent_recurrence_task_id: Optional[str] = None
    version: int = 1
    created_at: str
    updated_at: str
    completed_at: Optional[str] = None
    deleted_at: Optional[str] = None


class StateHistoryEvent(BaseModel):
    id: str
    task_id: str
    timestamp: str
    actor_client_id: str
    new_state: dict[str, Any]
    comment: str = ""


class TaskDocument(BaseModel):
    schema_version: str = Field(alias="$schema_version")
    client_id: str
    updated_at: str
    items: list[Task] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class RecurrenceRuleDocument(BaseModel):
    schema_version: str = Field(alias="$schema_version")
    items: list[RecurrenceRule] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class StateHistoryDocument(BaseModel):
    schema_version: str = Field(alias="$schema_version")
    events: list[StateHistoryEvent] = Field(default_factory=list)

    model_config = {"populate_by_name": True}
