# -*- coding: utf-8 -*-
# pyknic_todo/storage/helpers.py
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

"""Storage layer and abstractions for pyknic-todo conforming to STORAGE.md."""

# TODO: document the code
# TODO: write tests for the code

# TODO: reuse this code!

import uuid
import typing

from pyknic_todo.models import Task


def partial_uuid_select(entry_id: uuid.UUID, task_id_query: typing.Union[uuid.UUID, str]) -> bool:
    return str(entry_id).startswith(str(task_id_query))


def full_uuid_select(entry_id: uuid.UUID, task_id_query: typing.Union[uuid.UUID, str]) -> bool:
    return str(entry_id) == str(task_id_query)


def exact_one_task(
    tasks: typing.Iterable[Task],
    task_id_query: typing.Union[uuid.UUID, str],
    query_full_match: bool = True
) -> Task:
    check_fn = full_uuid_select if query_full_match else partial_uuid_select
    result = None
    for i in tasks:
        if check_fn(i.id, task_id_query):
            if result is not None:
                raise ValueError(f'Ambiguous task id: {task_id_query}')
            result = i

    if result is not None:
        return result

    raise KeyError(f'The task id {task_id_query} was not found')
