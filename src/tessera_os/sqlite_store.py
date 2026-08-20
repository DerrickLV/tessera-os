"""Opening SQLite on the filesystem production actually has.

The artifact store, the review queue and the audit chain are SQLite databases,
and in production they live on an Azure Files share so they survive a redeploy.
That share is SMB, and SMB is where SQLite's default assumptions stop holding.

**What actually fails, precisely.** SQLite coordinates access with POSIX
byte-range locks (``fcntl`` locks on regions of the database file). The Azure
Files SMB client does not implement them in a way SQLite can use, so the very
first ``CREATE TABLE`` on a brand-new, zero-byte, entirely uncontended database
raises ``sqlite3.OperationalError: database is locked``. There is no other
process. There is nothing to wait for. Waiting longer does not help, and the
first attempt at fixing this -- a thirty-second busy timeout -- only made the
failure take thirty seconds to arrive.

How it presented, which is worth recording because the symptom pointed
everywhere except the cause: the console raised at startup, the container
exited, Azure restarted it, and the revision never became healthy while the
previous one kept serving. It read as a code failure for most of an evening.

**The fix.** ``unix-dotfile`` replaces byte-range locking with an exclusive
lock *file* beside the database. Creating a file exclusively is an operation
SMB does implement, so the guarantee is real rather than absent -- this is not
"turn locking off", which is what ``unix-none`` would have done.

Dotfile locking is coarse, though: it excludes other *processes*, and within a
single process SQLite may hold the dotfile once while several connections
proceed behind it. Sync FastAPI endpoints run in a threadpool, so several
connections in one process is the normal case here, not an edge case. The
module-level lock below closes that gap by serializing every transaction in the
process. At two users and a single replica the cost is unmeasurable, and the
alternative is interleaved writes on a shared file.

**A single writer, still enforced.** ``maxReplicas`` is pinned to 1, and that
remains a correctness constraint rather than a cost decision -- dotfile locking
protects a database from concurrent processes, but two replicas writing an
SQLite file over SMB is a risk worth refusing outright. Removing the pin means
moving these stores to PostgreSQL first.

**Rollback journalling, stated rather than assumed.** WAL needs shared memory a
network filesystem does not provide. It is not enabled today, and saying so here
means enabling it later -- a reasonable-looking local optimisation -- cannot
quietly break production.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

# Generous, and now genuinely a timeout rather than a workaround: with dotfile
# locking a wait means another transaction is in flight, which is a thing worth
# waiting for.
BUSY_TIMEOUT_SECONDS = 30.0

# Byte-range locks are what SMB cannot do. A lock file is what it can.
VFS = "unix-dotfile"

# Dotfile locking excludes other processes; this excludes other threads within
# this one. Both are required, for different reasons -- see the module docstring.
_ACCESS = threading.RLock()


class _SerializedConnection(sqlite3.Connection):
    """A connection whose transactions are serialized process-wide.

    ``with connection:`` is SQLite's transaction block, so acquiring here means
    the lock is held for exactly as long as a transaction is open, and is
    released on commit or rollback rather than on garbage collection.
    """

    def __enter__(self) -> sqlite3.Connection:
        _ACCESS.acquire()
        try:
            return super().__enter__()
        except BaseException:
            _ACCESS.release()
            raise

    def __exit__(self, *exc_info: object) -> bool:
        try:
            return super().__exit__(*exc_info)  # type: ignore[arg-type]
        finally:
            _ACCESS.release()


def connect(path: Path | str) -> sqlite3.Connection:
    """Open a Tessera store, configured for a network filesystem."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    # The URI form is the only way to select a VFS from Python's sqlite3.
    connection = sqlite3.connect(f"file:{target}?vfs={VFS}", uri=True,
                                 timeout=BUSY_TIMEOUT_SECONDS,
                                 factory=_SerializedConnection)
    connection.row_factory = sqlite3.Row
    # DELETE, not WAL: WAL needs shared memory the share cannot offer, and the
    # resulting error names the database rather than the filesystem.
    connection.execute("PRAGMA journal_mode=DELETE")
    connection.execute(f"PRAGMA busy_timeout={int(BUSY_TIMEOUT_SECONDS * 1000)}")
    return connection
