
import pytest

from pyknic_todo.storage.proto import ToDoStorageProto, SchemeMigrationRequiredError, SchemeMigrationCallError


def test_exception() -> None:
    assert(issubclass(SchemeMigrationRequiredError, Exception) is True)
    assert(issubclass(SchemeMigrationCallError, Exception) is True)


def test_abstract() -> None:
    pytest.raises(TypeError, ToDoStorageProto)

    pytest.raises(NotImplementedError, ToDoStorageProto.create_storage, None)  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, ToDoStorageProto.load_tasks, None)  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, ToDoStorageProto.load_recurrence_rules, None)  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, ToDoStorageProto.load_states_history, None)  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, ToDoStorageProto.record_history_event, None, None)  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, ToDoStorageProto.record_task, None, None)  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, ToDoStorageProto.task_status, None, None)  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, ToDoStorageProto.storage_id, None)  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, ToDoStorageProto.latest_migration)
    pytest.raises(NotImplementedError, ToDoStorageProto.update_scheme, None)  # type: ignore[call-overload]

    with pytest.raises(NotImplementedError):
        ToDoStorageProto.set_task_status(None, None, None)  # type: ignore[arg-type]

    with pytest.raises(NotImplementedError):
        ToDoStorageProto.record_recurrence_rule(None, None)  # type: ignore[arg-type]

    with pytest.raises(NotImplementedError):
        ToDoStorageProto.set_task_recurrence(None, None)  # type: ignore[arg-type]
