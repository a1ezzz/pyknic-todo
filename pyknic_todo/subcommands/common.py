# -*- coding: utf-8 -*-
# pyknic_todo/subcommands/common.py
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

# TODO: tests

import typing

from pyknic_todo.version import __version__

from pyknic_todo.storage.proto import ToDoStorageProto
from pyknic_todo.models import Task

from .general_models import ToDoTasksListSelectModel, ToDoSingleTaskSelectModel


__plugin_version__ = f'pyknic-todo:{__version__}'


def select_single_task(storage: ToDoStorageProto, task_selector: ToDoSingleTaskSelectModel) -> Task:
    """Find a single task matching the given selector by ID prefix or exact title.

    :param storage: A storage to search
    :param task_selector: Task selector criteria (ID prefix or title).
    :return: Matched Task entity.
    :raises ValueError: If no matching task is found or if multiple tasks match.
    """

    task = None
    for t in storage.load_tasks():
        task_matched = False

        if task_selector.id and str(t.id).startswith(task_selector.id):
            task_matched = True

        if not task_matched and task_selector.title and t.title == task_selector.title:
            task_matched = True

        if not task_matched:
            continue

        if task is None:
            task = t
            continue

        raise ValueError('Multiple tasks spotted!')

    if task is None:
        raise ValueError('Unable to find a matching task')

    return task


def select_multiple_tasks(storage: ToDoStorageProto, task_selector: ToDoTasksListSelectModel) -> typing.List[Task]:
    """Find multiple tasks matching the given selectors by ID prefix or exact title.

    :param storage: A storage to search
    :param task_selector: Task selector criteria (ID prefix or title).
    :raises ValueError: If no matching task is found
    """

    tasks: typing.List[Task] = list()

    searching_titles = list(task_selector.title or [])
    searching_uids = list(task_selector.id or [])

    for t in storage.load_tasks():

        if any((x == t.title for x in searching_titles)):
            tasks.append(t)
            searching_titles.remove(t.title)
            continue

        matched_uid: typing.Optional[str] = None

        for i in searching_uids:
            if str(t.id).startswith(i):
                if matched_uid:
                    raise ValueError(f'Multiple tasks spotted for uid -- {i}!')
                matched_uid = i

        if matched_uid:
            tasks.append(t)
            searching_uids.remove(matched_uid)
            continue

    if searching_titles:
        raise ValueError(f'Unable to find a matching task for titles: {", ".join(searching_titles)}')

    if searching_uids:
        raise ValueError(f'Unable to find a matching task for UID\'s: {", ".join(searching_uids)}')

    return tasks
