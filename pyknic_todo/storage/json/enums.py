# -*- coding: utf-8 -*-
# pyknic_todo/storage/json/enums.py
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


import enum

from pyknic_todo.models import RecurrenceRule, StateUpdatedEvent, Task, ToDoStorageSettings, Project


@enum.unique
class JsonFile(enum.Enum):
    """Possible files that this storage creates."""

    tasks = "tasks.json"                        # file that stores :class:`.Task` objects
    projects = "projects.json"                  # file that stores :class:`.Project` objects
    recurrence_rules = "recurrence_rules.json"  # file that stores :class:`.RecurrenceRule` objects
    states_history = "states_history.json"      # file that stores :class:`.StateUpdatedEvent` objects
    settings = "settings.json"                  # file that stores :class:`.ToDoStorageSettings` object


@enum.unique
class JsonFileModels(enum.Enum):
    """Models that are stored in files."""
    tasks = Task
    projects = Project
    recurrence_rules = RecurrenceRule
    states_history = StateUpdatedEvent
    settings = ToDoStorageSettings
