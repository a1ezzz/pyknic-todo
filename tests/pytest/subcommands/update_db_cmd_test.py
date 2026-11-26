
import pathlib
import shutil
import tempfile

import pytest

from pyknic.lib.uri import URI

from pyknic_todo.cli import main

from pyknic_todo.storage.json.implementation import __json_storage_scheme__
from pyknic_todo.storage.proto import SchemeMigrationRequiredError


__unversioned_json_storage__ = pathlib.Path(__file__).parent / 'test-data-set' / 'unversioned'


def test_unupgraded_db() -> None:

    with tempfile.TemporaryDirectory(prefix='pytest-pyknic_todo', suffix='json_tmp_uri_fixture') as tmp_dir:

        tmp_path = pathlib.Path(tmp_dir)
        shutil.copytree(__unversioned_json_storage__, tmp_path / 'db')
        json_tmp_uri = URI.parse(f'{__json_storage_scheme__}:///{tmp_dir}/db')

        with pytest.raises(SchemeMigrationRequiredError):
            main([f"--storage-uri={str(json_tmp_uri)}", "list"])

        main([f"--storage-uri={str(json_tmp_uri)}", "update-db"])
        main([f"--storage-uri={str(json_tmp_uri)}", "list"])
