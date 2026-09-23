# pyknic-todo

**pyknic-todo** is a command-line task manager and BellBoy plugin written in Python. It provides structured task management with local JSON file storage (`json+file`), recurrence rule specifications (RRULE and Cron), and safe concurrent process access via file locking.

---

## Features

- **Core Task Management**: Create, list, inspect, update status, track history, and soft-delete tasks with title, description (Markdown-ready), priority, status, tags, and project associations.
- **Task Lifecycle**: Full lifecycle statuses:
  - `pending`: Ready to be worked on (default on creation).
  - `in_progress`: Currently being executed.
  - `done`: Completed.
  - `cancelled`: Cancelled.
  - `skipped`: Skipped (applicable to recurring tasks).
  - `deleted`: Soft-deleted.
- **Recurrence Support**: Define recurring schedules using RRULE (RFC 5545) or Cron expressions, with optional expiration date (`--until`).
- **Concurrent & Process-Safe**: Built-in file locking (`fcntl.flock`) on `.lock` to prevent race conditions or corrupted updates across concurrent CLI executions.
- **Task Selector**: Target tasks either by UUID / short UUID prefix (e.g. `c3b9e4a8`) using `--task.id`, or by exact title using `--task.title`.
- **Flexible List Filtering**: Default view displays existing tasks, with flags for status groups (`--active-tasks`, `--completed-tasks`, `--deleted-tasks`), as well as filters by `--id`, `--title`, `--project`, `--priority`, `--tags`, and `--max-age`.
- **Machine-Readable JSON Mode**: Global `--json-mode` flag for integrations, scripts, and CI/CD pipelines.
- **BellBoy & Pyknic Integration**: Seamless integration as a `pyknic` plugin exposing the `todo` command handler.

---

## Project Structure & Data Storage

Storage is specified via a storage URI with the `json+file` scheme (e.g. `json+file:///absolute/path/to/data`):

```
data/
├── tasks.json             # Tasks snapshot (newline-delimited JSON)
├── recurrence_rules.json  # Recurrence rule definitions (newline-delimited JSON)
├── states_history.json    # Append-only state transition audit log (newline-delimited JSON)
├── settings.json          # Storage metadata and client origin ID
└── .lock                  # Process lockfile for safe concurrency
```

### Storage Files Overview
- **`tasks.json`**: Newline-delimited JSON storing `Task` records (title, description, priority, tags, project, timestamps, recurrence rule ID).
- **`recurrence_rules.json`**: Newline-delimited JSON storing `RecurrenceRule` records (`schedule_type`, `schedule_expression`, optional `until_date`).
- **`states_history.json`**: Newline-delimited JSON storing `StateUpdatedEvent` records (`task_id`, `created_at`, `next_state`, `comment`, `storage_origin`).
- **`settings.json`**: Storage metadata storing `ToDoStorageSettings` (`id`, `comment`).
- **`.lock`**: File lock used by `StorageLock` (`fcntl.flock`) for atomic, process-safe operations.

---

## Installation

### Requirements
- Python 3.11+
- Linux / macOS (for POSIX file locking support)

### Setup Virtual Environment

```bash
# Clone the repository
git clone <repo-url>
cd pyknic-todo

# Create and activate virtual environment
virtualenv venv
source venv/bin/activate

# Install dependencies and editable package
pip install -r requirements.txt

# Or install with development & testing dependencies
pip install -e ".[dev,test]"
```

Once installed, the CLI command `pyknic-todo` will be available in your environment. You can also run the local launcher directly:

```bash
./pyknic-todo --help
# or
python -m pyknic_todo --help
```

---

## Storage Configuration

Pyknic-todo requires specifying the backend storage URI via the `--storage-uri` argument or through the `STORAGE-URI` environment variable:

```bash
# Using the CLI flag
pyknic-todo --storage-uri json+file:///absolute/path/to/data <command>

# Or export the environment variable
export STORAGE-URI="json+file:///absolute/path/to/data"
pyknic-todo <command>
```

---

## CLI Usage & Commands

### Global Options
- `--storage-uri <URI>`: Task storage backend URI (required, e.g. `json+file:///tmp/my-todos`).
- `--json-mode`: Print machine-readable JSON result instead of formatting console tables and strings.

### 1. Adding Tasks (`add`)

Create a new task:

```bash
# Basic task
pyknic-todo --storage-uri json+file:///tmp/my-todos add -t "Prepare release report"

# Task with description, priority, tags, and project
pyknic-todo --storage-uri json+file:///tmp/my-todos add \
  -t "Prepare release report" \
  --description "Verify metrics and aggregate logs" \
  -p high \
  --tags work,release,q3 \
  --project p-work-001
```

Available options:
- `-t, --title`: Title or summary of the task (**required**).
- `--description`: Detailed description (supports Markdown).
- `-p, --priority`: Priority level (`low`, `medium`, `high`, `urgent`). Default: `medium`.
- `--tags`: List of tags or labels (e.g. `--tags work,release`).
- `--project`: Optional project name for grouping related tasks.

### 2. Listing Tasks (`list`)

List and filter tasks in a formatted table:

```bash
# List all tasks
pyknic-todo --storage-uri json+file:///tmp/my-todos list

# Filter active tasks (pending or in_progress)
pyknic-todo --storage-uri json+file:///tmp/my-todos list --active-tasks

# Filter completed tasks (done, cancelled, skipped)
pyknic-todo --storage-uri json+file:///tmp/my-todos list --completed-tasks

# Filter soft-deleted tasks
pyknic-todo --storage-uri json+file:///tmp/my-todos list --deleted-tasks

# Filter by project, priority, or tags
pyknic-todo --storage-uri json+file:///tmp/my-todos list --project p-work-001 --priority high

# Filter tasks modified within the last N days
pyknic-todo --storage-uri json+file:///tmp/my-todos list --max-age 7

# Output tasks in JSON mode
pyknic-todo --storage-uri json+file:///tmp/my-todos --json-mode list
```

### 3. Showing Task Details (`show`)

Display detailed key-value metadata for a single task:

```bash
# Show by short UUID prefix
pyknic-todo --storage-uri json+file:///tmp/my-todos show --task.id c3b9e4a8

# Show by exact title
pyknic-todo --storage-uri json+file:///tmp/my-todos show --task.title "Prepare release report"

# Show details in JSON format
pyknic-todo --storage-uri json+file:///tmp/my-todos --json-mode show --task.id c3b9e4a8
```

### 4. Updating Task Status (`status`)

Change the status of an existing task using its ID prefix or title:

```bash
# Move task to in_progress with an explanatory comment
pyknic-todo --storage-uri json+file:///tmp/my-todos status \
  --task.id c3b9e4a8 \
  -s in_progress \
  --comment "Started preliminary audit"

# Mark task as cancelled
pyknic-todo --storage-uri json+file:///tmp/my-todos status \
  --task.id c3b9e4a8 \
  -s cancelled \
  --comment "Postponed indefinitely"
```

Available options:
- `--task.id`: Task identifier or UUID prefix.
- `--task.title`: Exact task title.
- `-s, --status`: New lifecycle status (`pending`, `in_progress`, `done`, `cancelled`, `skipped`, `deleted`) (**required**).
- `--comment`: Optional comment explaining the status transition.

### 5. Completing a Task (`done`)

Shorthand command to mark a task as completed (`done`):

```bash
pyknic-todo --storage-uri json+file:///tmp/my-todos done --task.id c3b9e4a8
pyknic-todo --storage-uri json+file:///tmp/my-todos done --task.id c3b9e4a8 --comment "Finished verification"
```

### 6. Configuring Recurrence (`repeat`)

Attach a recurrence schedule to a task:

```bash
# RRULE: Daily recurrence until a specific date
pyknic-todo --storage-uri json+file:///tmp/my-todos repeat \
  --task.id c3b9e4a8 \
  --schedule-type rrule \
  --schedule "FREQ=DAILY" \
  --until "2026-12-31T23:59:59Z"

# Cron: Run on Mondays at 10:00 AM indefinitely
pyknic-todo --storage-uri json+file:///tmp/my-todos repeat \
  --task.id c3b9e4a8 \
  --schedule-type cron \
  --schedule "0 10 * * 1"
```

Available options:
- `--task.id` or `--task.title`: Target task selector (**required**).
- `--schedule-type`: Schedule format (`rrule` or `cron`) (**required**).
- `--schedule`: RRULE expression string or Cron expression (**required**).
- `--until`: Optional ISO-formatted datetime expiration for the schedule.

### 7. Task Status History (`history`)

Display the audit log of status transitions for a task:

```bash
# Show recent status history (default depth: 10)
pyknic-todo --storage-uri json+file:///tmp/my-todos history --task.id c3b9e4a8

# Show history with custom depth
pyknic-todo --storage-uri json+file:///tmp/my-todos history --task.id c3b9e4a8 -d 5
```

### 8. Deleting a Task (`delete`)

Soft-delete an existing task:

```bash
pyknic-todo --storage-uri json+file:///tmp/my-todos delete --task.id c3b9e4a8
```

---

## Allowed Values & Schemas

### Statuses
- `pending`: Task is ready for execution (initial status).
- `in_progress`: Task is actively being worked on.
- `done`: Task has been completed.
- `cancelled`: Task was cancelled.
- `skipped`: Occurrence was skipped (for recurring tasks).
- `deleted`: Task was soft-deleted.

### Priorities
- `low`
- `medium` (default)
- `high`
- `urgent`

### Recurrence Schedule Types
- `rrule`: RFC 5545 iCalendar recurrence rule (e.g. `FREQ=DAILY`, `FREQ=WEEKLY;BYDAY=MO,WE,FR`).
- `cron`: Standard cron schedule format (e.g. `0 10 * * 1`, `0 12 * * *`).

---

## Development & Testing

Run unit tests and generate test coverage reports:

```bash
venv/bin/pytest
```

Run code style and lint checks:

```bash
venv/bin/flake8
```

Run static type checking:

```bash
venv/bin/mypy pyknic_todo
```

---

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.
