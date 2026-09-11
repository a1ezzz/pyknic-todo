# pyknic-todo

**pyknic-todo** is a reliable command-line task manager written in Python. It provides structured task management with local JSON storage, recurrence rule specifications (RRULE and Cron), and safe concurrent file access using file locks.

---

## Features

- **Core Task Management**: Create, list and update tasks with title, description (Markdown-ready), priority, status, due date, tags, and project associations.
- **Rich Status Lifecycle**: Support for full lifecycle statuses:
  - `new`: Scheduled for the future.
  - `pending`: Ready to be worked on (default).
  - `in_progress`: Currently being executed.
  - `done`: Completed.
  - `cancelled`: Cancelled.
  - `skipped`: Skipped (for recurring tasks).
  - `deleted`: Soft-deleted.
- **Recurrence Support**: Define recurring schedules using RRULE (RFC 5545) or Cron expressions, with configurable end conditions (`never`, `until_date`, or `count`).
- **Concurrent & Process-Safe**: Built-in file locking (`fcntl.flock`) and atomic write mechanisms to prevent race conditions or corrupted updates across concurrent CLI executions.
- **ID Prefix Resolution**: Reference tasks by short UUID prefixes (e.g. `c3b9e4a8` instead of the full UUID).
- **Flexible List Filtering**: Default view displays active tasks (hiding completed and deleted), with flags for `--all`, `--completed`, `--include-completed`, `--status`, and raw `--json` output for scripting.
- **Extensible Configuration**: Configurable via CLI arguments, environment variables (`PYKNIC_TODO_*` / `TODO_DATA_DIR`), or `.env` files via Pydantic Settings.

---

## Project Structure & Data Storage

By default, data is stored in the `./data/` directory (or custom directory specified via `--data-dir` or `PYKNIC_TODO_DATA_DIR`):

```
data/
├── tasks.json             # Current task items snapshot
├── recurrence_rules.json  # Recurrence rule definitions
├── states_history.json    # Append-only state transition audit log
└── .lock                  # Process lockfile for safe concurrency
```

### File Schema Overview
- **`tasks.json`**: Tracks `$schema_version`, unique `client_id`, last modification timestamp `updated_at`, and task records.
- **`recurrence_rules.json`**: Stores schedules (`rrule` or `cron`) and completion conditions (`never`, `until_date`, `count`).
- **`states_history.json`**: Keeps an audit log of state changes (`new_state`, `timestamp`, `actor_client_id`, `comment`).

---

## Installation

### Requirements
- Python 3.9+
- Linux / macOS (for POSIX file locking support)

### Setup Virtual Environment

```bash
# Clone the repository
git clone <repo-url>
cd pyknic-todo

# Create and activate virtual environment
virtualenv .venv
source .venv/bin/activate

# Install dependencies and editable package
pip install -r requirements.txt
```

Once installed, the CLI command `pyknic-todo` will be available in your environment. You can also run the local launcher directly:

```bash
./pyknic-todo --help
# or
python3 -m pyknic_todo --help
```

---

## Configuration

Configuration is managed via Pydantic Settings and can be supplied through environment variables or a `.env` file:

| Setting | Environment Variable(s) | Default | Description |
|---|---|---|---|
| `data_dir` | `PYKNIC_TODO_DATA_DIR`, `TODO_DATA_DIR` | `./data` | Directory where JSON files are stored |
| `default_priority` | `PYKNIC_TODO_DEFAULT_PRIORITY` | `medium` | Default priority for newly created tasks |
| `default_status` | `PYKNIC_TODO_DEFAULT_STATUS` | `pending` | Default status for newly created tasks |

### Inspect Configuration
Display active configuration settings:

```bash
pyknic-todo config
```

Or in JSON format:

```bash
pyknic-todo config --json
```

---

## CLI Usage & Commands

### 1. Adding Tasks (`add`)

Create a new task:

```bash
# Basic task
pyknic-todo add "Prepare release report"

# Task with description, priority, tags, project, and due date
pyknic-todo add "Prepare release report" \
  -d "Verify metrics and aggregate logs" \
  -p high \
  -t work,release,q3 \
  --project p-work-001 \
  --due "2026-09-15T18:00:00Z"
```

Available options:
- `-d, --description`: Extended description (supports Markdown).
- `-p, --priority`: Priority (`low`, `medium`, `high`, `urgent`). Default: `medium`.
- `-s, --status`: Initial status (`new`, `pending`, `in_progress`, etc.). Default: `pending`.
- `-t, --tag`: Tag (can be repeated or comma-separated: `-t work -t dev` or `-t work,dev`).
- `--project`: Project ID string.
- `--due, --due-date`: Due date in ISO format.

### 2. Listing Tasks (`list`)

List tasks in a formatted table:

```bash
# List active tasks (excludes completed and deleted)
pyknic-todo list

# Show all tasks including completed and deleted
pyknic-todo list --all
# or shorthand
pyknic-todo list -a

# Show only completed tasks
pyknic-todo list --completed
# or shorthand
pyknic-todo list -c

# Include completed tasks with active tasks
pyknic-todo list --include-completed

# Filter by a specific status
pyknic-todo list -s in_progress

# Output tasks as JSON (useful for integrations, jq, or scripts)
pyknic-todo list --json
```

### 3. Updating Task Status (`status`)

Change the status of a task using its ID or unique ID prefix:

```bash
# Move task to in_progress with a comment
pyknic-todo status c3b9e4a8 in_progress -m "Started preliminary audit"

# Mark task as cancelled
pyknic-todo status c3b9e4a8 cancelled -m "Postponed indefinitely"
```

### 4. Completing a Task (`done`)

Shorthand command to mark a task as completed (`done`):

```bash
pyknic-todo done c3b9e4a8
pyknic-todo done c3b9e4a8 -m "Finished verification"
```

### 5. Configuring Recurrence (`repeat`)

Attach a recurrence schedule to a task:

```bash
# RRULE: Weekly recurrence on Monday, Wednesday, Friday until a specific date
pyknic-todo repeat c3b9e4a8 \
  --type rrule \
  -e "FREQ=WEEKLY;BYDAY=MO,WE,FR" \
  --end-type until_date \
  --until "2026-12-31T23:59:59Z"

# Cron: Run on weekdays at 10:00 AM, up to 10 occurrences
pyknic-todo repeat c3b9e4a8 \
  --type cron \
  -e "0 10 * * 1-5" \
  --end-type count \
  --count 10

# Indefinite recurrence
pyknic-todo repeat c3b9e4a8 \
  -e "FREQ=DAILY" \
  --end-type never
```

Options:
- `-e, --expression`: RRULE expression string or Cron expression (**required**).
- `-t, --type`: Schedule format (`rrule` or `cron`). Default: `rrule`.
- `--end-type`: End condition (`never`, `until_date`, `count`). Default: `never`.
- `--until`: ISO formatted end date for `until_date`.
- `--count`: Maximum occurrences for `count`.

### Custom Data Directory

Specify a custom data directory for any command using `--data-dir`:

```bash
pyknic-todo --data-dir /tmp/my-todo list
```

---

## Allowed Values & Schemas

### Statuses
- `new`
- `pending`
- `in_progress`
- `done`
- `cancelled`
- `skipped`
- `deleted`

### Priorities
- `low`
- `medium`
- `high`
- `urgent`

### Recurrence Schedule Types
- `rrule` (RFC 5545 RRULE format)
- `cron` (standard 5-part cron syntax)

### Recurrence End Condition Types
- `never`
- `until_date`
- `count`

---

## Development & Testing

Run unit tests using `pytest` within the project virtual environment:

```bash
.venv/bin/pytest
```

Run test suite with verbose output:

```bash
.venv/bin/pytest -v
```

---

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.
