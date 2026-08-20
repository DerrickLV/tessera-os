"""Opening SQLite the way production's filesystem requires.

These stores live on an Azure Files share so they outlive a redeploy. SMB is
where SQLite's defaults stop holding, and the way that surfaced was not a
corrupt database but a container that would not start: the review queue raised
``database is locked`` at import, the container exited, Azure restarted it, and
the restart met the same lock the dead process had not yet released. The
revision never became healthy, the previous one kept serving, and the symptom
read as a code failure.
"""

from __future__ import annotations

import pytest

from tessera_os.automation import ActionControlStore
from tessera_os.review import ReviewQueue
from tessera_os.runtime_controls import RuntimeAuditStore
from tessera_os.sqlite_store import BUSY_TIMEOUT_SECONDS, connect
from tessera_os.workspace import PilotArtifactStore


def test_journalling_is_rollback_not_wal(tmp_path):
    """WAL needs shared memory a network filesystem does not provide, and a WAL
    database on SMB fails at open with an error that names the database rather
    than the filesystem."""
    with connect(tmp_path / "store.db") as connection:
        mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "delete"


def test_locking_uses_a_lock_file_rather_than_byte_ranges(tmp_path):
    """The whole cause, in one assertion.

    SQLite coordinates with POSIX byte-range locks, which the Azure Files SMB
    client does not implement usefully: the first CREATE TABLE on a new,
    zero-byte, entirely uncontended database raises "database is locked".
    Creating a lock file exclusively is something SMB does implement, so the
    guarantee stays real instead of being switched off.
    """
    from tessera_os.sqlite_store import VFS
    assert VFS == "unix-dotfile"
    path = tmp_path / "store.db"
    with connect(path) as connection:
        connection.execute("CREATE TABLE t (id INTEGER)")
    assert path.exists()


def test_transactions_are_serialized_within_the_process(tmp_path):
    """Dotfile locking excludes other processes but not other threads in this
    one, and sync endpoints run in a threadpool -- so several connections in one
    process is the normal case, not an edge case."""
    import threading

    path = tmp_path / "store.db"
    with connect(path) as setup:
        setup.execute("CREATE TABLE t (id INTEGER)")

    overlaps = []
    inside = threading.Event()

    def writer(value: int) -> None:
        with connect(path) as connection:
            overlaps.append(inside.is_set())
            inside.set()
            connection.execute("INSERT INTO t VALUES (?)", (value,))
            inside.clear()

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not any(overlaps), "two transactions were open at once"
    with connect(path) as check:
        assert check.execute("SELECT count(*) FROM t").fetchone()[0] == 8


def test_the_busy_timeout_outlasts_an_smb_lock_handover(tmp_path):
    """Now genuinely a timeout rather than a workaround: with dotfile locking a
    wait means another transaction is in flight."""
    with connect(tmp_path / "store.db") as connection:
        timeout_ms = connection.execute("PRAGMA busy_timeout").fetchone()[0]
    assert timeout_ms == int(BUSY_TIMEOUT_SECONDS * 1000)
    assert BUSY_TIMEOUT_SECONDS >= 30


def test_a_store_survives_being_reopened_after_an_unclean_exit(tmp_path):
    """The failure left a zero-byte database behind, and every restart met it.
    Reopening one must recover rather than inherit the previous run's problem."""
    path = tmp_path / "store.db"
    path.write_bytes(b"")
    with connect(path) as connection:
        connection.execute("CREATE TABLE t (id INTEGER)")
        connection.execute("INSERT INTO t VALUES (1)")
    with connect(path) as reopened:
        assert reopened.execute("SELECT count(*) FROM t").fetchone()[0] == 1


@pytest.mark.parametrize("store", [ReviewQueue, PilotArtifactStore,
                                   RuntimeAuditStore, ActionControlStore])
def test_every_durable_store_opens_through_the_shared_connector(tmp_path, store):
    """One store left on the defaults is enough to reproduce the crash loop, so
    this asserts the property for all of them rather than for the one that
    happened to fail."""
    instance = store(tmp_path / f"{store.__name__}.db")
    # Reaching into _connect is the point: the property must hold for the
    # store as constructed, not for a connection the test opens itself.
    with instance._connect() as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "delete"
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == int(
            BUSY_TIMEOUT_SECONDS * 1000)
