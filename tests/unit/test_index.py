"""Unit tests for stratum.index — SQLite dedup index (STRAT-107)."""

from pathlib import Path

import pytest

from stratum.index import (
    DeletionPathIncorrectException,
    PathRequiredToDeleteDBException,
    StratumIndex,
)

# ---------------------------------------------------------------------------
# Context manager behaviour
# ---------------------------------------------------------------------------


class TestContextManager:
    def test_enters_and_exits_cleanly(self, tmp_path):
        db = tmp_path / "index.db"
        with StratumIndex(db_path=db) as idx:
            assert idx is not None

    def test_connection_closed_after_exit(self, tmp_path):
        db = tmp_path / "index.db"
        with StratumIndex(db_path=db) as idx:
            conn = idx._conn

        # After __exit__ the connection should be closed; any operation raises
        with pytest.raises(Exception):
            conn.execute("SELECT 1")

    def test_connection_closed_on_exception(self, tmp_path):
        db = tmp_path / "index.db"
        conn_ref = None
        with pytest.raises(RuntimeError):
            with StratumIndex(db_path=db) as idx:
                conn_ref = idx._conn
                raise RuntimeError("boom")

        # Connection must be closed even though an exception was raised
        with pytest.raises(Exception):
            conn_ref.execute("SELECT 1")


# ---------------------------------------------------------------------------
# contains() — unknown hash returns None
# ---------------------------------------------------------------------------


class TestContainsUnknown:
    def test_unknown_hash_returns_none(self, tmp_path):
        db = tmp_path / "index.db"
        with StratumIndex(db_path=db) as idx:
            result = idx.contains("deadbeef" * 8)
            assert result is None

    def test_different_hash_returns_none(self, tmp_path):
        db = tmp_path / "index.db"
        known_hash = "a" * 64
        other_hash = "b" * 64
        with StratumIndex(db_path=db) as idx:
            idx.insert(known_hash, Path("/some/file.txt"))
            assert idx.contains(other_hash) is None


# ---------------------------------------------------------------------------
# insert() then contains() returns the path string
# ---------------------------------------------------------------------------


class TestInsertThenContains:
    def test_contains_returns_path_after_insert(self, tmp_path):
        db = tmp_path / "index.db"
        h = "a" * 64
        p = Path("/home/user/docs/report.pdf")
        with StratumIndex(db_path=db) as idx:
            idx.insert(h, p)
            result = idx.contains(h)
        assert result == str(p)

    def test_contains_returns_string_not_path(self, tmp_path):
        db = tmp_path / "index.db"
        h = "c" * 64
        p = Path("/tmp/file.txt")
        with StratumIndex(db_path=db) as idx:
            idx.insert(h, p)
            result = idx.contains(h)
        assert isinstance(result, str)

    def test_multiple_hashes_independent(self, tmp_path):
        db = tmp_path / "index.db"
        h1, h2 = "1" * 64, "2" * 64
        p1, p2 = Path("/a/one.txt"), Path("/b/two.txt")
        with StratumIndex(db_path=db) as idx:
            idx.insert(h1, p1)
            idx.insert(h2, p2)
            assert idx.contains(h1) == str(p1)
            assert idx.contains(h2) == str(p2)


# ---------------------------------------------------------------------------
# Inserting the same hash twice does not raise
# ---------------------------------------------------------------------------


class TestInsertDuplicate:
    def test_duplicate_insert_does_not_raise(self, tmp_path):
        db = tmp_path / "index.db"
        h = "d" * 64
        p = Path("/dup/file.txt")
        with StratumIndex(db_path=db) as idx:
            idx.insert(h, p)
            idx.insert(h, p)  # should be silent

    def test_duplicate_insert_keeps_original_path(self, tmp_path):
        db = tmp_path / "index.db"
        h = "e" * 64
        p_first = Path("/first/file.txt")
        p_second = Path("/second/file.txt")
        with StratumIndex(db_path=db) as idx:
            idx.insert(h, p_first)
            idx.insert(h, p_second)  # INSERT OR IGNORE — first path is kept
            result = idx.contains(h)
        assert result == str(p_first)


# ---------------------------------------------------------------------------
# SQLite file created at the specified path, including missing parent dirs
# ---------------------------------------------------------------------------


class TestDatabaseCreation:
    def test_db_file_created_at_specified_path(self, tmp_path):
        db = tmp_path / "index.db"
        assert not db.exists()
        with StratumIndex(db_path=db):
            pass
        assert db.exists()

    def test_missing_parent_dirs_created(self, tmp_path):
        db = tmp_path / "deep" / "nested" / "dir" / "index.db"
        assert not db.parent.exists()
        with StratumIndex(db_path=db):
            pass
        assert db.exists()


# ---------------------------------------------------------------------------
# No shared state between tests (each test uses its own tmp_path db)
# ---------------------------------------------------------------------------


class TestIsolation:
    def test_fresh_db_has_no_entries(self, tmp_path):
        db = tmp_path / "index.db"
        with StratumIndex(db_path=db) as idx:
            assert idx.contains("f" * 64) is None

    def test_data_persists_across_context_manager_sessions(self, tmp_path):
        db = tmp_path / "index.db"
        h = "9" * 64
        p = Path("/persistent/file.bin")

        with StratumIndex(db_path=db) as idx:
            idx.insert(h, p)

        # Re-open the same db and check persistence
        with StratumIndex(db_path=db) as idx:
            assert idx.contains(h) == str(p)


# ---------------------------------------------------------------------------
# Parameterised queries — verify no SQL injection via string formatting
# ---------------------------------------------------------------------------


class TestParameterisedQueries:
    def test_hash_with_sql_injection_chars_is_stored_safely(self, tmp_path):
        db = tmp_path / "index.db"
        # If queries use f-strings this would break; parameterised handles it fine
        h = "0" * 64
        p = Path("/path/with'; DROP TABLE hashes; --/file.txt")
        with StratumIndex(db_path=db) as idx:
            idx.insert(h, p)
            result = idx.contains(h)
        assert result == str(p)

    def test_hashes_table_survives_malicious_path(self, tmp_path):
        db = tmp_path / "index.db"
        h = "1" * 64
        p = Path("/safe/file.txt")
        malicious_hash = "'; DROP TABLE hashes; --"
        with StratumIndex(db_path=db) as idx:
            idx.insert(h, p)
            # This should return None, not destroy the table
            result = idx.contains(malicious_hash)
        assert result is None

        # The hashes table must still exist and return the original entry
        with StratumIndex(db_path=db) as idx:
            assert idx.contains(h) == str(p)


# ---------------------------------------------------------------------------
# del_db() — happy path
# ---------------------------------------------------------------------------


class TestDelDbSuccess:
    def test_del_db_removes_the_file(self, tmp_path):
        db = tmp_path / "index.db"
        with StratumIndex(db_path=db) as idx:
            assert db.exists()
            idx.del_db(path=db)
        assert not db.exists()

    def test_del_db_accepts_matching_path(self, tmp_path):
        db = tmp_path / "index.db"
        with StratumIndex(db_path=db) as idx:
            idx.del_db(path=db)  # must not raise


# ---------------------------------------------------------------------------
# del_db() — PathRequiredToDeleteDBException
# ---------------------------------------------------------------------------


class TestDelDbNoPath:
    def test_raises_when_path_is_none(self, tmp_path):
        db = tmp_path / "index.db"
        with StratumIndex(db_path=db) as idx:
            with pytest.raises(PathRequiredToDeleteDBException):
                idx.del_db(path=None)

    def test_raises_when_path_is_empty_string(self, tmp_path):
        db = tmp_path / "index.db"
        with StratumIndex(db_path=db) as idx:
            with pytest.raises(PathRequiredToDeleteDBException):
                idx.del_db(path="")

    def test_exception_message_mentions_path(self):
        exc = PathRequiredToDeleteDBException()
        assert "Path required" in str(exc)

    def test_file_not_deleted_when_no_path_given(self, tmp_path):
        db = tmp_path / "index.db"
        with StratumIndex(db_path=db) as idx:
            try:
                idx.del_db(path=None)
            except PathRequiredToDeleteDBException:
                pass
        assert db.exists()


# ---------------------------------------------------------------------------
# del_db() — DeletionPathIncorrectException
# ---------------------------------------------------------------------------


class TestDelDbWrongPath:
    def test_raises_when_path_does_not_match(self, tmp_path):
        db = tmp_path / "index.db"
        wrong = tmp_path / "other.db"
        with StratumIndex(db_path=db) as idx:
            with pytest.raises(DeletionPathIncorrectException):
                idx.del_db(path=wrong)

    def test_exception_message_contains_correct_path(self, tmp_path):
        db = tmp_path / "index.db"
        exc = DeletionPathIncorrectException(db)
        assert str(db) in str(exc)

    def test_file_not_deleted_when_wrong_path_given(self, tmp_path):
        db = tmp_path / "index.db"
        wrong = tmp_path / "other.db"
        with StratumIndex(db_path=db) as idx:
            try:
                idx.del_db(path=wrong)
            except DeletionPathIncorrectException:
                pass
        assert db.exists()
