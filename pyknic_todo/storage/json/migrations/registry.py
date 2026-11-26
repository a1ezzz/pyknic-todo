# -*- coding: utf-8 -*-
# pyknic_todo/storage/json/migrations/registry.py
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

# TODO: test it

import datetime
import json
import pathlib
import types
import typing

from pyknic.lib.registry import APIRegistry, register_api

from pyknic_todo.storage.json.enums import JsonFile
from pyknic_todo.storage.json.helpers import read_jsonl_file


__json_migrations_registry__ = APIRegistry()


class JSONLMigrationHelper:
    """ This class helps to upgrade (migrate) JSONL files
    """

    def __init__(self, file_path: pathlib.Path, write_mode: bool = True):
        """ Create a new migration helper

        :param file_path: file to upgrade or to read
        :param write_mode: whether changes must be written at the end or not
        """

        self.__file_path = file_path if write_mode else None
        self.__entries: typing.List[typing.Dict[str, typing.Any]] = []

        for i in read_jsonl_file(file_path):
            self.__entries.append(json.loads(i))

    def entries(self) -> typing.List[typing.Dict[str, typing.Any]]:
        """ Return entries stored in a file
        """
        return self.__entries

    def deduplicate_entries(
        self,
        key_field: str,
        comparison_fn: typing.Callable[[typing.Dict[str, typing.Any], typing.Dict[str, typing.Any]], bool]
    ) -> typing.List[typing.Dict[str, typing.Any]]:
        """ Return deduplicated entries that was stored in a file

        :param key_field: this is a field name. By that field multiple rows will be deduplicated and the only
        one will be returned.
        :param comparison_fn: a function that helps to choose one row that should be kept. This function returns
        True when the first row must be choosen or False for the second one.
        """
        filtered_entries: typing.Dict[typing.Any, typing.Dict[str, typing.Any]] = dict()

        for i in self.__entries:
            entry_key = i[key_field]

            prev_entry = filtered_entries.get(entry_key)
            if prev_entry is None or not comparison_fn(prev_entry, i):
                filtered_entries[entry_key] = i

        return list(filtered_entries.values())

    def mutate(self, mutator: typing.Callable[[typing.Dict[str, typing.Any]], typing.Dict[str, typing.Any]]) -> None:
        """ This function helps to update rows

        :param mutator: function that converts previous (unmigrated) row to a newer version of it
        """
        new_entries = []
        for i in self.__entries:
            new_entries.append(mutator(i))
        self.__entries = new_entries

    def __enter__(self) -> 'JSONLMigrationHelper':
        """ Enter the context
        """
        return self

    def __exit__(
        self,
        exc_type: typing.Optional[typing.Type[BaseException]],
        exc: typing.Optional[BaseException],
        tb: typing.Optional[types.TracebackType]
    ) -> None:
        """ Exit the context and write down changes if require
        """
        if self.__file_path is not None:
            with self.__file_path.open('w') as f:
                for i in self.__entries:
                    f.write(json.dumps(i))
                    f.write('\n')


@register_api(__json_migrations_registry__, '0.0.8')
def migrate_to_v0_0_8(storage_path: pathlib.Path) -> None:
    """ Migrate from unversionized "pre-0.0.8" version to the "0.0.8" (but unversionized still)

    :param storage_path: database path
    """

    # There was a bug, that overrwrites storage id with every call
    # So since we do not support synchronization at this version it is OK
    # to overwrite this

    with (storage_path / JsonFile.settings.value).open('r') as f:
        settings_data = json.load(f)

        if 'scheme_version' in settings_data:
            raise RuntimeError(f'This migration is not suitable for the "{settings_data["scheme_version"]}" version')

    with (storage_path / JsonFile.settings.value).open() as f:
        settings_data = json.load(f)
        storage_id = settings_data['id']

        if 'scheme_version' in settings_data:
            raise RuntimeError(f'This migration is not suitable for the "{settings_data["scheme_version"]}" version')

    with JSONLMigrationHelper(storage_path / JsonFile.tasks.value) as m:

        def task_mutator(task: typing.Dict[str, typing.Any]) -> typing.Dict[str, typing.Any]:
            task['storage_origin'] = storage_id
            return task

        m.mutate(task_mutator)

    with JSONLMigrationHelper(storage_path / JsonFile.states_history.value) as m:

        def history_mutator(state: typing.Dict[str, typing.Any]) -> typing.Dict[str, typing.Any]:
            state['storage_origin'] = storage_id
            return state

        m.mutate(history_mutator)

    # It is better to save the version 0.0.8 to database, but there was not any versioning at the 0.0.8 release


@register_api(__json_migrations_registry__, '0.0.10')
def migrate_to_v0_0_10(storage_path: pathlib.Path) -> None:
    """ Migrate from unversionized "0.0.8" version to the "0.0.10"

    :param storage_path: database path
    """

    # There was not a scheme versioning, so we will apply this

    with (storage_path / JsonFile.settings.value).open('r') as f:
        settings_data = json.load(f)

        if 'scheme_version' in settings_data:
            raise RuntimeError(f'This migration is not suitable for the "{settings_data["scheme_version"]}" version')

    states: typing.Dict[str, typing.Dict[str, typing.Any]] = dict()
    with JSONLMigrationHelper(storage_path / JsonFile.states_history.value, write_mode=False) as m:

        def comparison_fn(state1: typing.Dict[str, typing.Any], state2: typing.Dict[str, typing.Any]) -> bool:
            state1_dt = datetime.datetime.fromisoformat(state1['created_at'])
            state2_dt = datetime.datetime.fromisoformat(state2['created_at'])
            return state1_dt > state2_dt

        for state_json in m.deduplicate_entries('task_id', comparison_fn):
            states[state_json['task_id']] = state_json

    with JSONLMigrationHelper(storage_path / JsonFile.tasks.value) as m:

        def task_mutator(task: typing.Dict[str, typing.Any]) -> typing.Dict[str, typing.Any]:
            if task['id'] not in states:
                raise RuntimeError('There is no state information in the database (but the must be)')
            task['state_id'] = states[task['id']]['id']
            return task

        m.mutate(task_mutator)

    with (storage_path / JsonFile.settings.value).open('w') as f:
        settings_data['scheme_version'] = '0.0.10'
        json.dump(settings_data, f)
