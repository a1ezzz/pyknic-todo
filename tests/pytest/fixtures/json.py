
import tempfile
import typing

import pytest

from pyknic.lib.uri import URI

from pyknic_todo.storage.json import __json_storage_scheme__


@pytest.fixture
def json_tmp_uri() -> typing.Generator[URI, None, None]:

    with tempfile.TemporaryDirectory(prefix='pytest-pyknic_todo', suffix='json_tmp_uri_fixture') as tmp_dir:
        yield URI.parse(f'{__json_storage_scheme__}:///{tmp_dir}')
