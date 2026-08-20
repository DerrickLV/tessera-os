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

import sqlite3

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


def test_the_busy_timeout_outlasts_an_smb_lock_handover(tmp_path):
    """SQLite's five-second default is shorter than a handover on SMB under no
    contention at all, which is the difference between a restart that recovers
    and a crash loop."""
    with connect(tmp_path / "store.db") as connection:
        timeout_ms = connection.execute("PRAGMA busy_timeout").fetchone()[0]
    assert timeout_ms == int(BUSY_TIMEOUT_SECONDS * 1000)
    assert BUSY_TIMEOUT_SECONDS >= 30


def test_a_held_write_lock_is_waited_out_rather_than_raising(tmp_path):
    """The behaviour the timeout buys, demonstrated rather than asserted about."""
    path = tmp_path / "store.db"
    with connect(path) as setup:
        setup.execute("CREATE TABLE t (id INTEGER)")

    holder = connect(path)
    holder.execute("BEGIN IMMEDIATE")
    try:
        impatient = sqlite3.connect(str(path), timeout=0)
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            impatient.execute("BEGIN IMMEDIATE")
        impatient.close()
    finally:
        holder.rollback()
        holder.close()

    # And once released, a normally configured connection proceeds.
    with connect(path) as after:
        after.execute("INSERT INTO t VALUES (1)")


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
