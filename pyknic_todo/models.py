"""Data models validated with Pydantic."""

# TODO: refactor this
# TODO: add client_id somewhere! (it should be persistent somehow)

from __future__ import annotations

import uuid

from datetime import datetime, timezone

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

VALID_PRIORITIES = {"low", "medium", "high", "urgent"}

VALID_STATUSES = {
    "new",
    "pending",
    "in_progress",
    "done",
    "cancelled",
    "skipped",
    "deleted",
}

VALID_SCHEDULE_TYPES = {"rrule", "cron"}
VALID_END_CONDITIONS = {"never", "until_date", "count"}


def get_utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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

    @staticmethod
    def create(
        schedule_type: str,
        schedule_expression: str,
        end_condition_type: str = "never",
        until_date: Optional[str] = None,
        max_occurrences: Optional[int] = None,
    ) -> 'RecurrenceRule':

        # TODO: is this ok, or better to use direct RecurrenceRule() call?

        if schedule_type not in VALID_SCHEDULE_TYPES:
            raise ValueError(f"Invalid schedule_type '{schedule_type}'. Valid: {sorted(VALID_SCHEDULE_TYPES)}")
        if end_condition_type not in VALID_END_CONDITIONS:
            raise ValueError(
                f"Invalid end_condition_type '{end_condition_type}'. Valid: {sorted(VALID_END_CONDITIONS)}"
            )

        rule_id = f"rec-rule-{uuid.uuid4().hex[:8]}"
        now = get_utc_now_iso()
        return RecurrenceRule(
            id=rule_id,
            schedule_type=schedule_type,  # type: ignore[arg-type]
            schedule_expression=schedule_expression.strip(),
            end_condition=EndCondition(
                type=end_condition_type,  # type: ignore[arg-type]
                until_date=until_date,
                max_occurrences=max_occurrences,
            ),
            created_at=now,
        )


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

    @staticmethod
    def create(
        title: str,
        priority: str,
        status: str,
        description: str = "",
        due_date: Optional[str] = None,
        tags: Optional[list[str]] = None,
        project_id: Optional[str] = None,
    ) -> 'Task':

        # TODO: is this ok, or better to use direct Task() call?

        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status '{status}'. Valid statuses: {sorted(VALID_STATUSES)}")
        if priority not in VALID_PRIORITIES:
            raise ValueError(f"Invalid priority '{priority}'. Valid priorities: {sorted(VALID_PRIORITIES)}")

        now = get_utc_now_iso()
        task_id = str(uuid.uuid4())
        task_obj = Task(
            id=task_id,
            project_id=project_id,
            title=title.strip(),
            description=description.strip() if description else "",
            status=status,
            priority=priority,
            due_date=due_date,
            tags=tags or [],
            recurrence_rule_id=None,
            parent_recurrence_task_id=None,
            version=1,
            created_at=now,
            updated_at=now,
            completed_at=now if status == "done" else None,
            deleted_at=now if status == "deleted" else None,
        )

        return task_obj


class StateHistoryEvent(BaseModel):
    id: str
    task_id: str
    timestamp: str
    actor_client_id: str
    new_state: dict[str, Any]
    comment: str = ""

    @staticmethod
    def create(
        task_id: str,
        new_state: dict[str, Any],
        actor_client_id: Optional[str] = None,
        comment: Optional[str] = None
    ) -> 'StateHistoryEvent':
        client_id = actor_client_id or str(uuid.uuid4())  # TODO: client_id should be persistent somewhere!
        return StateHistoryEvent(
            id=f"evt-{uuid.uuid4()}",
            task_id=task_id,
            timestamp=get_utc_now_iso(),
            actor_client_id=client_id,
            new_state=new_state,
            comment=comment or "",
        )


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
