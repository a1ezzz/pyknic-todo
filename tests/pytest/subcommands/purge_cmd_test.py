
import typing

from pyknic.lib.uri import URI

from pyknic_todo.models import Task
from pyknic_todo.storage.proto import ToDoStorageProto
from pyknic_todo.storage.json.implementation import JsonStorage
from pyknic_todo.cli import main


def populate_storage(storage: ToDoStorageProto) -> None:
    # TODO: may be better to do it with main
    storage.record_task(Task(title='Task1'))
    storage.record_task(Task(title='Task2'))


def storage_statistics(storage: JsonStorage) -> typing.Tuple[int, int, int]:

    tasks_rows = len(storage._tasks()._read_json())
    rules_rows = len(storage._recurrence_rules()._read_json())
    history_rows = len(storage._history()._read_json())

    return (tasks_rows, rules_rows, history_rows)


def test_purge_as_is(json_tmp_uri: URI) -> None:
    storage_arg = f"--storage-uri={str(json_tmp_uri)}"
    storage = JsonStorage(json_tmp_uri)

    populate_storage(storage)
    assert(storage_statistics(storage) == (2, 0, 2))

    main([storage_arg, "purge"])
    assert(storage_statistics(storage) == (2, 0, 2))  # nothing changed

    main([storage_arg, "purge", "--no-remove-deleted"])
    assert(storage_statistics(storage) == (2, 0, 2))  # nothing changed

    task = storage.load_tasks()[0]
    main([storage_arg, "delete", "--task.id", str(task.id)])
    main([storage_arg, "purge", "--no-remove-deleted"])
    assert(storage_statistics(storage) == (3, 0, 3))  # states and tasks updated, but there are tasks still

    main([storage_arg, "purge"])
    assert(storage_statistics(storage) == (1, 0, 1))  # purge happens

    main([storage_arg, "purge", "--remove-completed"])
    assert(storage_statistics(storage) == (1, 0, 1))  # nothing changed

    main([storage_arg, "purge", "--reduce-history"])
    assert(storage_statistics(storage) == (1, 0, 1))  # nothing changed


def test_purge_completed(json_tmp_uri: URI) -> None:
    storage_arg = f"--storage-uri={str(json_tmp_uri)}"
    storage = JsonStorage(json_tmp_uri)

    populate_storage(storage)
    assert(storage_statistics(storage) == (2, 0, 2))

    task = storage.load_tasks()[0]
    main([storage_arg, "done", "--task.id", str(task.id)])
    main([storage_arg, "purge", "--no-remove-completed"])
    assert(storage_statistics(storage) == (3, 0, 3))  # states and tasks updated, but there are tasks still

    main([storage_arg, "purge"])
    assert(storage_statistics(storage) == (3, 0, 3))  # nothing changed

    main([storage_arg, "purge", "--remove-completed"])
    assert(storage_statistics(storage) == (1, 0, 1))  # purge happens

    main([storage_arg, "purge", "--reduce-history"])
    assert(storage_statistics(storage) == (1, 0, 1))  # nothing changed


def test_purge_completed_w_endless_rrule(json_tmp_uri: URI) -> None:
    storage_arg = f"--storage-uri={str(json_tmp_uri)}"
    storage = JsonStorage(json_tmp_uri)

    populate_storage(storage)
    assert(storage_statistics(storage) == (2, 0, 2))

    task = storage.load_tasks()[0]
    main([storage_arg, "done", "--task.id", str(task.id)])
    main([storage_arg, "repeat", "--task.id", str(task.id), "--schedule-type", "cron", "--schedule", "0 * * * *"])
    main([storage_arg, "purge", "--no-remove-completed"])
    assert(storage_statistics(storage) == (4, 1, 3))  # states and tasks updated, but there are tasks still

    main([storage_arg, "purge"])
    assert(storage_statistics(storage) == (4, 1, 3))  # nothing changed

    main([storage_arg, "purge", "--remove-completed"])
    assert(storage_statistics(storage) == (4, 1, 3))  # nothing changed (because there is a recurrency rule)

    main([storage_arg, "purge", "--reduce-history"])
    assert(storage_statistics(storage) == (2, 1, 2))  # something purged


def test_purge_completed_w_future_end_rrule(json_tmp_uri: URI) -> None:
    storage_arg = f"--storage-uri={str(json_tmp_uri)}"
    storage = JsonStorage(json_tmp_uri)

    populate_storage(storage)
    assert(storage_statistics(storage) == (2, 0, 2))

    task = storage.load_tasks()[0]
    main([storage_arg, "done", "--task.id", str(task.id)])
    main([
        storage_arg,
        "repeat",
        "--task.id",
        str(task.id),
        "--schedule-type",
        "cron",
        "--schedule",
        "0 * * * *",
        "--until",
        "3000-12-31T23:59:59Z"
    ])
    main([storage_arg, "purge", "--no-remove-completed"])
    assert(storage_statistics(storage) == (4, 1, 3))  # states and tasks updated, but there are tasks still

    main([storage_arg, "purge"])
    assert(storage_statistics(storage) == (4, 1, 3))  # nothing changed

    main([storage_arg, "purge", "--remove-completed"])
    assert(storage_statistics(storage) == (4, 1, 3))  # nothing changed (because there is a recurrency rule)

    main([storage_arg, "purge", "--reduce-history"])
    assert(storage_statistics(storage) == (2, 1, 2))  # something purged


def test_purge_completed_w_past_end_rrule(json_tmp_uri: URI) -> None:
    storage_arg = f"--storage-uri={str(json_tmp_uri)}"
    storage = JsonStorage(json_tmp_uri)

    populate_storage(storage)
    assert(storage_statistics(storage) == (2, 0, 2))

    task = storage.load_tasks()[0]
    main([storage_arg, "done", "--task.id", str(task.id)])
    main([
        storage_arg,
        "repeat",
        "--task.id",
        str(task.id),
        "--schedule-type",
        "cron",
        "--schedule",
        "0 * * * *",
        "--until",
        "2000-12-31T23:59:59Z"
    ])
    main([storage_arg, "purge", "--no-remove-completed"])
    assert(storage_statistics(storage) == (4, 1, 3))  # states and tasks updated, but there are tasks still

    main([storage_arg, "purge"])
    assert(storage_statistics(storage) == (4, 1, 3))  # nothing changed

    main([storage_arg, "purge", "--remove-completed"])
    assert(storage_statistics(storage) == (1, 0, 1))  # purge happens

    main([storage_arg, "purge", "--reduce-history"])
    assert(storage_statistics(storage) == (1, 0, 1))  # nothing changed


def test_purge_uncompleted_w_past_end_rrule(json_tmp_uri: URI) -> None:
    storage_arg = f"--storage-uri={str(json_tmp_uri)}"
    storage = JsonStorage(json_tmp_uri)

    populate_storage(storage)
    assert(storage_statistics(storage) == (2, 0, 2))

    task = storage.load_tasks()[0]
    main([
        storage_arg,
        "repeat",
        "--task.id",
        str(task.id),
        "--schedule-type",
        "cron",
        "--schedule",
        "0 * * * *",
        "--until",
        "2000-12-31T23:59:59Z"
    ])
    main([storage_arg, "purge", "--no-remove-completed"])
    assert(storage_statistics(storage) == (3, 1, 2))  # states and tasks updated, but there are tasks still

    main([storage_arg, "purge"])
    assert(storage_statistics(storage) == (3, 1, 2))  # nothing changed

    main([storage_arg, "purge", "--remove-completed"])
    assert(storage_statistics(storage) == (3, 1, 2))  # nothing changed, because task wasn't completed

    main([storage_arg, "purge", "--reduce-history"])
    assert(storage_statistics(storage) == (2, 1, 2))  # nothing changed
