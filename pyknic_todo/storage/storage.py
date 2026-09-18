# -*- coding: utf-8 -*-
# pyknic_todo/storage/storage.py
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
# TODO: may be it is better to search with a search engine that works in conjuction with storage engine. This may help to:
#   - not to load JSON files multiple times!
#   - not to load everything from SQL-a-like storages

from __future__ import annotations


from .json import JsonStorage


# TODO: update registry!

StorageFactory = {
    "json": JsonStorage
}
