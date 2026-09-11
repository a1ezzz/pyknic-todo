
# Task Management (Core)

1. Basic CRUD: create, view, edit, delete, and mark as complete.
2. Possible task states:
- new (task scheduled for the future)
- pending (task ready for execution)
- in_progress (task currently being worked on)
- done (task completed)
- cancelled (task cancelled)
- skipped (task skipped — state applicable only to recurring tasks)
- deleted (task deleted)
3. Task attributes:
- Title and detailed description (Markdown support). 
- Deadline (date and time). 
- Priorities (e.g., low, medium, high, urgent). 
- Tags/categories and lists/projects (e.g., @work, @personal). 
- Recurrence rules for recurring tasks.
4. Search and filtering: filters by status (completed, pending), date, and tags; full-text search.
5. Change log (what was changed and when).
6. Task list stored separately from the state change history.

# Recurring tasks

1. Recurrence rule options:
- RRULE (RFC 5545): daily, on weekdays, weekly, monthly, Nth day of the month, yearly. 
- Cron: cron format =)
2. Fixed schedule: the next date is generated strictly according to the schedule (e.g., the 1st of every month).
3. Relative interval: the next date is calculated based on the actual completion time of the task (+N days).
4. End conditions: indefinite, until a specific date, or after a set number of repetitions.

# Synchronization and Backend

1. Offline-first mode
2. Cross-device synchronization: Automatic synchronization between the CLI and the web interface via a centralized REST API/WebSocket backend
3. Ability to create and modify tasks without an internet connection
4. Local caching and automatic background synchronization upon network reconnection
5. Ability to synchronize multiple sources (more than two), including local files and a centralized server
6. Standardized data exchange format for synchronization, explicitly specifying the format version
7. Various synchronization policies:
- One-way with merging
- One-way with replacement
- Two-way
8. Conflict resolution: basic strategy (e.g., Last Write Wins, vector clocks/CRDTs for lists, or timestamp-based version tracking)

# Command-Line Interface (CLI)

1. Command mode: quick command entry, e.g.:
- todo add "Buy milk" --due tomorrow --repeat weekly
- todo list --today --tag work
- todo done <id>
- Interactive TUI mode (Terminal UI): pseudo-graphic interface with arrow-key navigation and hotkeys.
2. Script integration: JSON export/output.
3. Authentication: `todo login` command with token storage in `~/.config/todo/config.json`.
4. Shell completions: support for Bash, Zsh, and Fish.

# Web UI
- Responsive design: fully functional on both desktop and mobile devices.
- Hotkeys: keyboard shortcuts for rapid task creation and mouse-free navigation.
- Dark and light themes.
- User profile (time zone, language, date format).

# Notifications and Export
- Reminders: OS-level system notifications and Web Push/email alerts for urgent deadlines.
- Backup and export: Data import/export in JSON, CSV, or Markdown/Todo.txt formats.
