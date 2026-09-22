
import typing
import uuid

import pytest

from pyknic_todo.models import Task
from pyknic_todo.storage.helpers import exact_one_task, full_uuid_select, partial_uuid_select


class TestPartialUuidSelect:

    def test_exact_uuid(self) -> None:
        target_id = uuid.uuid4()
        assert(partial_uuid_select(target_id, target_id) is True)

    def test_exact_str(self) -> None:
        target_id = uuid.uuid4()
        assert(partial_uuid_select(target_id, str(target_id)) is True)

    def test_prefix_match(self) -> None:
        target_id = uuid.uuid4()
        prefix = str(target_id)[:8]
        assert(partial_uuid_select(target_id, prefix) is True)
        assert(partial_uuid_select(target_id, "") is True)

    def test_mismatch(self) -> None:
        target_id = uuid.uuid4()
        other_id = uuid.uuid4()
        assert(partial_uuid_select(target_id, other_id) is False)
        assert(partial_uuid_select(target_id, "nonexistent") is False)

    def test_longer_than_uuid(self) -> None:
        target_id = uuid.uuid4()
        extended = f"{target_id}-extra"
        assert(partial_uuid_select(target_id, extended) is False)


class TestFullUuidSelect:

    def test_exact_uuid(self) -> None:
        target_id = uuid.uuid4()
        assert(full_uuid_select(target_id, target_id) is True)

    def test_exact_str(self) -> None:
        target_id = uuid.uuid4()
        assert(full_uuid_select(target_id, str(target_id)) is True)

    def test_prefix_does_not_match(self) -> None:
        target_id = uuid.uuid4()
        prefix = str(target_id)[:8]
        assert(full_uuid_select(target_id, prefix) is False)
        assert(full_uuid_select(target_id, "") is False)

    def test_mismatch(self) -> None:
        target_id = uuid.uuid4()
        other_id = uuid.uuid4()
        assert(full_uuid_select(target_id, other_id) is False)
        assert(full_uuid_select(target_id, "nonexistent") is False)


class TestExactOneTask:

    def test_full_match_uuid(self) -> None:
        task1 = Task(title="First")
        task2 = Task(title="Second")
        result = exact_one_task([task1, task2], task1.id)
        assert(result == task1)

    def test_full_match_str(self) -> None:
        task1 = Task(title="First")
        task2 = Task(title="Second")
        result = exact_one_task([task1, task2], str(task2.id))
        assert(result == task2)

    def test_full_match_prefix_fails(self) -> None:
        task1 = Task(title="First")
        prefix = str(task1.id)[:8]
        with pytest.raises(KeyError, match=f"The task id {prefix} was not found"):
            exact_one_task([task1], prefix, query_full_match=True)

    def test_full_match_not_found(self) -> None:
        task1 = Task(title="First")
        missing_id = uuid.uuid4()
        with pytest.raises(KeyError, match=f"The task id {missing_id} was not found"):
            exact_one_task([task1], missing_id)

    def test_empty_tasks(self) -> None:
        missing_id = uuid.uuid4()
        with pytest.raises(KeyError, match=f"The task id {missing_id} was not found"):
            exact_one_task([], missing_id)

    def test_full_match_ambiguous(self) -> None:
        task_id = uuid.uuid4()
        task1 = Task(id=task_id, title="Task 1")
        task2 = Task(id=task_id, title="Task 2")
        with pytest.raises(ValueError, match=f"Ambiguous task id: {task_id}"):
            exact_one_task([task1, task2], task_id, query_full_match=True)

    def test_partial_match_prefix_success(self) -> None:
        id1 = uuid.UUID("11111111-1111-1111-1111-111111111111")
        id2 = uuid.UUID("22222222-2222-2222-2222-222222222222")
        task1 = Task(id=id1, title="Task 1")
        task2 = Task(id=id2, title="Task 2")
        result = exact_one_task([task1, task2], "11111111", query_full_match=False)
        assert(result == task1)

    def test_partial_match_full_uuid(self) -> None:
        task1 = Task(title="Task 1")
        task2 = Task(title="Task 2")
        result = exact_one_task([task1, task2], task2.id, query_full_match=False)
        assert(result == task2)

    def test_partial_match_ambiguous(self) -> None:
        id1 = uuid.UUID("aaaaaaaa-1111-1111-1111-111111111111")
        id2 = uuid.UUID("aaaaaaaa-2222-2222-2222-222222222222")
        task1 = Task(id=id1, title="Task 1")
        task2 = Task(id=id2, title="Task 2")
        with pytest.raises(ValueError, match="Ambiguous task id: aaaaaaaa"):
            exact_one_task([task1, task2], "aaaaaaaa", query_full_match=False)

    def test_partial_match_not_found(self) -> None:
        task1 = Task(title="Task 1")
        with pytest.raises(KeyError, match="The task id zzz was not found"):
            exact_one_task([task1], "zzz", query_full_match=False)

    def test_iterable_generator(self) -> None:
        task1 = Task(title="First")
        task2 = Task(title="Second")

        def task_gen() -> typing.Iterator[Task]:
            yield task1
            yield task2

        result = exact_one_task(task_gen(), task1.id)
        assert(result == task1)
