
import pytest

from pyknic_todo.storage.proto import ToDoStorageProto


def test_abstract() -> None:
    pytest.raises(TypeError, ToDoStorageProto)

    pytest.raises(NotImplementedError, ToDoStorageProto.create_storage, None)  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, ToDoStorageProto.load_tasks, None)  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, ToDoStorageProto.save_tasks, None, [])  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, ToDoStorageProto.load_recurrence_rules, None)  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, ToDoStorageProto.save_recurrence_rules, None, [])  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, ToDoStorageProto.load_history, None)  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, ToDoStorageProto.record_history_event, None, None)  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, ToDoStorageProto.append_task, None, None)  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, ToDoStorageProto.task_status, None, None)  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, ToDoStorageProto.storage_id, None)  # type: ignore[call-overload]
    with pytest.raises(NotImplementedError):
        ToDoStorageProto.set_task_status(None, None, None)  # type: ignore[arg-type]
    pytest.raises(  # type: ignore[call-overload]
        NotImplementedError, ToDoStorageProto.set_task_recurrence, None, None
    )
