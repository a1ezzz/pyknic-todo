
# JSON (messagepack?) storage scheme (local files)
Recommended data directory structure (~/.local/share/todo/ or a local directory):
data/
├── tasks.json             # Current task list (current snapshot)
├── recurrence_rules.json  # Recurrence rules (separate or embedded in the task)
├── states_history.json    # State change log

## tasks.json (tasks list)
{
  "$schema_version": "1.0.0",
  "client_id": "cli-device-uuid-1234",
  "updated_at": "2026-09-10T14:30:00Z",
  "items": [
    {
      "id": "c3b9e4a8-6f12-4e89-a29f-7e8c3b9e4a81",
      "project_id": "p-work-001",
      "title": "Do the report",
      "description": "## Some details\n Check metrics",
      "status": "pending", 
      "priority": "high",
      "due_date": "2026-09-15T18:00:00Z",
      "tags": ["work", "report"],
      
      "recurrence_rule_id": "rec-rule-001",
      "parent_recurrence_task_id": null,
      
      "version": 4,
      "created_at": "2026-09-01T10:00:00Z",
      "updated_at": "2026-09-10T14:30:00Z",
      "completed_at": null,
      "deleted_at": null
    }
  ]
}

Possible values:
 - for status: "new", "pending", "in_progress", "done", "cancelled", "skipped", "deleted".  
 - for priority: "low", "medium", "high", "urgent".

## recurrence_rules.json
{
  "$schema_version": "1.0.0",
  "items": [
    {
      "id": "rec-rule-001",
      "schedule_type": "rrule",
      "schedule_expression": "FREQ=WEEKLY;BYDAY=MO,WE,FR",
      "end_condition": {
        "type": "until_date",
        "until_date": "2026-12-31T23:59:59Z",
        "max_occurrences": null
      },
      "created_at": "2026-09-01T10:00:00Z"
    },
    {
      "id": "rec-rule-002",
      "schedule_type": "cron",
      "schedule_expression": "0 10 * * 1-5",
      "end_condition": {
        "type": "count",
        "until_date": null,
        "max_occurrences": 10
      },
      "created_at": "2026-09-02T11:00:00Z"
    }
  ]
}

- schedule_type: "rrule" | "cron"
- end_condition.type: "never" | "until_date" | "count"

## states_history.json (audit and state change log)
{
  "$schema_version": "1.0.0",
  "events": [
    {
      "id": "evt-0001",
      "task_id": "c3b9e4a8-6f12-4e89-a29f-7e8c3b9e4a81",
      "timestamp": "2026-09-10T14:30:00Z",
      "actor_client_id": "cli-device-uuid-1234",
      "new_state": { "status": "done" },
      "comment": "Completed via CLI"
    }
  ]
}

# SQL storage schema (PostgreSQL / SQLite compatible)

# 1. Projects / lists

CREATE TABLE projects (
    id VARCHAR(36) PRIMARY KEY, -- UUID
    name VARCHAR(255) NOT NULL,
    color VARCHAR(32),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

# 2. Repetition rules for recurrent tasks

CREATE TABLE recurrence_rules (
    id VARCHAR(36) PRIMARY KEY,
    schedule_type VARCHAR(16) NOT NULL CHECK (schedule_type IN ('rrule', 'cron')),
    schedule_expression VARCHAR(255) NOT NULL,
    interval_mode VARCHAR(16) NOT NULL CHECK (interval_mode IN ('fixed', 'relative')),
    relative_offset_days INTEGER DEFAULT 0,
    end_condition_type VARCHAR(16) NOT NULL CHECK (end_condition_type IN ('never', 'until_date', 'count')),
    until_date TIMESTAMP WITH TIME ZONE,
    max_occurrences INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

# 3. Tasks

CREATE TABLE tasks (
    id VARCHAR(36) PRIMARY KEY,
    project_id VARCHAR(36) REFERENCES projects(id) ON DELETE SET NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'new' CHECK (
        status IN ('new', 'pending', 'in_progress', 'done', 'cancelled', 'skipped', 'deleted')
    ),
    priority VARCHAR(10) NOT NULL DEFAULT 'medium' CHECK (
        priority IN ('low', 'medium', 'high', 'urgent')
    ),
    due_date TIMESTAMP WITH TIME ZONE,
    
    -- Recursion links
    recurrence_rule_id VARCHAR(36) REFERENCES recurrence_rules(id) ON DELETE SET NULL,
    parent_recurrence_task_id VARCHAR(36) REFERENCES tasks(id) ON DELETE SET NULL,
    
    -- Synchronization and metadata
    version INTEGER NOT NULL DEFAULT 1,
    client_id VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for filtering and search
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_due_date ON tasks(due_date);
CREATE INDEX idx_tasks_project ON tasks(project_id);
CREATE INDEX idx_tasks_updated_at ON tasks(updated_at); -- For quick retrieval of synchronization diffs

# 4. Tags (normalized M:N relationship)

CREATE TABLE tags (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL
);

CREATE TABLE task_tags (
    task_id VARCHAR(36) NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    tag_id VARCHAR(36) NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (task_id, tag_id)
);

# 5. Separate log of state changes and events (Audit Log)

CREATE TABLE task_state_history (
    id VARCHAR(36) PRIMARY KEY,
    task_id VARCHAR(36) NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    actor_client_id VARCHAR(64) NOT NULL,
    event_type VARCHAR(32) NOT NULL, -- 'status_changed', 'edited', 'skipped', etc.
    old_status VARCHAR(20),
    new_status VARCHAR(20),
    changes_json TEXT,                -- delta of modified fields in JSON
    comment TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_history_task_id ON task_state_history(task_id, created_at);

# 6. Synchronization state (for offline/online replication and LWW)

CREATE TABLE sync_cursors (
    source_id VARCHAR(64) PRIMARY KEY, -- Remote/local source ID
    last_synced_version INTEGER NOT NULL,
    last_synced_at TIMESTAMP WITH TIME ZONE NOT NULL
);