"""Opening SQLite on the filesystem production actually has.

The artifact store, the review queue and the audit chain are SQLite databases,
and in production they live on an Azure Files share so they survive a redeploy.
That share is SMB, and SMB is where SQLite's default assumptions stop holding.

The failure this exists to prevent, in the order it happened:

1. The console opened the review queue at startup and raised
   ``sqlite3.OperationalError: database is locked``.
2. The container exited, Azure restarted it, and the restart hit the same lock
   — because the previous process's byte-range lock had not been released on
   the share yet.
3. Every subsequent restart re-armed the same condition, so the revision never
   became healthy and the previous revision kept serving. The deployment looked
   like a code failure and was a filesystem one.

Three settings, each for a distinct reason:

**A real busy timeout.** SQLite's default is five seconds, and on SMB a lock
handover can take longer than that under no contention at all. Thirty seconds
costs nothing when the lock is free and is the difference between a restart
that recovers and a crash loop.

**Rollback journalling, stated explicitly rather than assumed.** WAL requires
shared memory that a network filesystem does not provide, so a WAL database on
SMB fails at open. It is not enabled today, and writing it down means enabling
it later — a reasonable-looking local optimisation — cannot silently break
production.

**A single writer, enforced.** ``maxReplicas`` is pinned to 1 for exactly this
reason, and it is a correctness constraint rather than a cost decision.
Removing that pin requires moving these stores to PostgreSQL first; SQLite over
SMB with two writers corrupts rather than errors.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

# Generous, because the cost of waiting is nothing and the cost of not waiting
# is a container that never becomes healthy.
BUSY_TIMEOUT_SECONDS = 30.0


def connect(path: Path | str) -> sqlite3.Connection:
    """Open a Tessera store, configured for a network filesystem."""
    connection = sqlite3.connect(str(path), timeout=BUSY_TIMEOUT_SECONDS)
    connection.row_factory = sqlite3.Row
    # DELETE, not WAL: WAL needs shared memory the share cannot offer, and the
    # resulting error names the database rather than the filesystem.
    connection.execute("PRAGMA journal_mode=DELETE")
    connection.execute(f"PRAGMA busy_timeout={int(BUSY_TIMEOUT_SECONDS * 1000)}")
    return connection
