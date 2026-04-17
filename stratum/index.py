"""Dedup index — persists content hashes in a local SQLite database."""

import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_DDL = """
CREATE TABLE IF NOT EXISTS hashes (
    hash       TEXT PRIMARY KEY,
    path       TEXT NOT NULL,
    indexed_at TEXT NOT NULL
);"""


logger = logging.getLogger(__name__)


class PathRequiredToDeleteDBException(Exception):
    """Exception created as a guardrail.

    It is not technically required to have the path to delete the DB since its path is in the obj,
    but deleting a DB is a dangerous operation, and we need to ensure users are certain they want
    to delete the DB
    """

    def __str__(self):
        return "Path required to delete DB. Do you really want to delete it?"


class DeletionPathIncorrectException(Exception):
    """Exception created as a guardrail.

    It is not technically required to have the path to delete the DB since its path is in the obj,
    but deleting a DB is a dangerous operation. By ensuring the paths are the same we can force
    the user to be certain in their operations.
    """

    def __str__(self):
        return f"Path passed for deletion is not correct should be {self.args}."


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
        except Exception as e:
            logger.error("Exception with sqlite connection:", e)
            self.__exit__()
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

    def del_db(self, path: Path) -> None:
        """Deleting the DB allows us clear out results from previous scans.

        I am worried about the situation where we scan one dir, retain everything in the index,
        then scan a different dir and we report everything as a duplicate that it should be
        deleted. I think this is not how stratum should work across separate runs.
        """
        # if path not provided raise
        if not path:
            raise PathRequiredToDeleteDBException()
        if path != self._path:
            raise DeletionPathIncorrectException(self._path)

        logger.info("deleting index at %s", path)
        os.remove(path)
