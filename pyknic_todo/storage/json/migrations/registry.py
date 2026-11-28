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
import os
import pathlib
import types
import typing
import uuid

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
                    f.write(json.dumps(i, ensure_ascii=False))
                    f.write('\n')


@register_api(__json_migrations_registry__, '0.0.8')
def migrate_to_v0_0_8(storage_path: pathlib.Path) -> None:
    """ Migrate from unversionized "pre-0.0.8" version to the "0.0.8" (but unversionized still)

    Changes:
      - There was a bug, that overrwrites storage id with every call.
        So since we do not support synchronization at this version it is OK
        to overwrite this

    :param storage_path: database path
    """

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

    Changes:
      - the new field for every task -- "status_id"
      - the new field for a storage settings -- "scheme_version"

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
        json.dump(settings_data, f, ensure_ascii=False)


@register_api(__json_migrations_registry__, '0.0.11')
def migrate_to_v0_0_11(storage_path: pathlib.Path) -> None:
    """ Migrate from the "0.0.10" version to the "0.0.11"

    Changes:
      - a new dedicated storage for projects
      - the field 'project' for every task was replaced by 'project_id'

    :param storage_path: database path
    """

    with (storage_path / JsonFile.settings.value).open() as f:
        current_settings = json.load(f)
        current_version = current_settings['scheme_version']
        if current_version != '0.0.10':
            raise RuntimeError(f'Unable to migrate from the "{current_version}" version')

    projects: typing.Set[str] = set()
    with JSONLMigrationHelper(storage_path / JsonFile.tasks.value, write_mode=False) as m:

        for task_json in m.entries():
            if task_json['project'] is not None:
                projects.add(task_json['project'])

    inserted_projects: typing.Dict[str, uuid.UUID] = dict()
    with (storage_path / JsonFile.projects.value).open('w') as f:
        for p in projects:
            project_id = uuid.uuid4()
            f.write(json.dumps(
                {"id": str(project_id), "name": p, "storage_origin": current_settings['id']},
                ensure_ascii=False
            ))
            f.write('\n')

            inserted_projects[p] = project_id

    with JSONLMigrationHelper(storage_path / JsonFile.tasks.value) as m:

        def task_mutator(task: typing.Dict[str, typing.Any]) -> typing.Dict[str, typing.Any]:
            project = task.pop('project')
            task['project_id'] = str(inserted_projects[project]) if project is not None else None
            return task

        m.mutate(task_mutator)

    with (storage_path / JsonFile.settings.value).open('w') as f:
        current_settings['scheme_version'] = '0.0.11'
        json.dump(current_settings, f, ensure_ascii=False)


@register_api(__json_migrations_registry__, '0.0.13')
def migrate_to_v0_0_13(storage_path: pathlib.Path) -> None:
    """ Migrate from the "0.0.11" version to the "0.0.13"

    Changes:
      - There was a bug that corrupts tasks states. A triggered recurrency
        rule did create a new state, but did not update state_id, version or update_dt for a task

    :param storage_path: database path
    """

    with (storage_path / JsonFile.settings.value).open() as f:
        current_settings = json.load(f)
        current_version = current_settings['scheme_version']
        if current_version != '0.0.11':
            raise RuntimeError(f'Unable to migrate from the "{current_version}" version')

    states_history: typing.Dict[uuid.UUID, typing.List[typing.Dict[str, typing.Any]]] = dict()
    with JSONLMigrationHelper(storage_path / JsonFile.states_history.value, write_mode=False) as m:

        for state_json in m.entries():
            sh = states_history.get(state_json['task_id'], list())
            sh.append(state_json)
            states_history[state_json['task_id']] = sh

    tasks_history: typing.Dict[uuid.UUID, typing.List[typing.Dict[str, typing.Any]]] = dict()
    with JSONLMigrationHelper(storage_path / JsonFile.tasks.value, write_mode=False) as m:

        for task_json in m.entries():
            th = tasks_history.get(task_json['id'], list())
            th.append(task_json)
            tasks_history[task_json['id']] = th

    new_task_rows = []
    for task_json in m.entries():
        state_history_per_task = states_history[task_json['id']]

        latest_task_history = tasks_history[task_json['id']][-1]
        latest_state_history = state_history_per_task[-1]

        if latest_task_history['state_id'] == latest_state_history['id']:
            # do not change anything if there was a successfull and clean state update before
            continue

        if latest_task_history['updated_at'] > latest_state_history['created_at']:
            # do not change anything there were changes
            continue

        # we should find the latest commited changes
        latest_commit = -1
        for i, state_json in enumerate(states_history[task_json['id']]):
            if state_json['id'] == latest_task_history['state_id']:
                latest_commit = i
                break

        if latest_commit < 0:
            raise RuntimeError('Internal logic error! Please, consider to check and/or submit a github issue!')

        version_increment = 1
        for state_json in state_history_per_task[latest_commit + 1:]:
            new_row = latest_task_history.copy()
            new_row['state_id'] = state_json['id']
            new_row['version'] += version_increment
            new_row['updated_at'] = state_json['created_at']

            new_task_rows.append(new_row)

            version_increment += 1

    with (storage_path / JsonFile.tasks.value).open('a') as f:
        f.seek(0, os.SEEK_END)

        for r in new_task_rows:
            f.write(json.dumps(r, ensure_ascii=False))
            f.write('\n')

    with (storage_path / JsonFile.settings.value).open('w') as f:
        current_settings['scheme_version'] = '0.0.13'
        json.dump(current_settings, f, ensure_ascii=False)
