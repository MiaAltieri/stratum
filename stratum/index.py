"""Dedup index — persists content hashes in a local SQLite database."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_DDL = """
CREATE TABLE IF NOT EXISTS hashes (
    hash       TEXT PRIMARY KEY,
    path       TEXT NOT NULL,
    indexed_at TEXT NOT NULL
);"""


class StratumIndex:
    def __init__(self, db_path: Path = Path(__file__).parent / "index.db"):
        self._path = db_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def __enter__(self) -> "StratumIndex":
        try:
            self._conn = sqlite3.connect(self._path, check_same_thread=False)
            self._conn.execute(_DDL)
            self._conn.commit()
            return self
        except Exception:
            if self._conn:
                self._conn.close()  # don't leak connections on failures
            raise

    def __exit__(self, *_) -> None:
        if self._conn:
            self._conn.close()

    def contains(self, content_hash: str) -> str | None:
        """Return the original path if hash is known, else None."""
        cursor = self._conn.execute("SELECT path FROM hashes WHERE hash = ?", (content_hash,))
        row = cursor.fetchone()
        if row:
            return row[0]

        return None

    def insert(self, content_hash: str, path: Path) -> None:
        """Record a new hash. Silently ignores duplicates."""
        self._conn.execute(
            "INSERT OR IGNORE INTO hashes (hash, path, indexed_at) VALUES (?, ?, ?)",
            (content_hash, str(path), datetime.now(timezone.utc).isoformat()),
        )
        self._conn.commit()
