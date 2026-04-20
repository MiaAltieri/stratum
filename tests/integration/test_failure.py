"""Integration tests: failure handling and error recovery."""

import os
import stat
from pathlib import Path
from unittest.mock import patch

import pytest

import stratum.index as _index_module
import stratum.main as _main_module
from stratum.index import (
    DeletionPathIncorrectException,
    PathRequiredToDeleteDBException,
    StratumIndex,
)
from stratum.exceptions import DirNotFoundException
from stratum.main import (
    PID_FILE_NAME,
    _process_directory,
    _run_stratum,
)
from stratum.suggestion_log import CalledOutsideContextManager, SuggestionLogger

from tests.integration.helpers import make_stratum_config, write_file, CONTENT_A

_DB_PATH = Path(_index_module.__file__).parent / "index.db"
_PID_PATH = Path(_main_module.__file__).parent / PID_FILE_NAME


@pytest.mark.integration
class TestNonExistentDirectory:
    def test_config_with_nonexistent_watch_dir_raises_dir_not_found(self, tmp_path):
        with pytest.raises(DirNotFoundException):
            make_stratum_config(
                watch_dirs=[tmp_path / "does_not_exist"],
                suggestions_dir=tmp_path,
            )

    def test_config_error_message_contains_missing_path(self, tmp_path):
        missing = tmp_path / "ghost_dir"
        with pytest.raises(DirNotFoundException, match=str(missing)):
            make_stratum_config(
                watch_dirs=[missing],
                suggestions_dir=tmp_path,
            )

    def test_config_rejects_file_path_as_watch_dir(self, tmp_path):
        not_a_dir = tmp_path / "file.txt"
        not_a_dir.write_text("I am a file")
        with pytest.raises(DirNotFoundException):
            make_stratum_config(
                watch_dirs=[not_a_dir],
                suggestions_dir=tmp_path,
            )


@pytest.mark.integration
class TestPermissionDeniedDirectory:
    @pytest.fixture()
    def locked_dir(self, tmp_path):
        d = tmp_path / "locked"
        d.mkdir()
        write_file(d / "secret.txt", CONTENT_A)
        os.chmod(d, stat.S_IRUSR)  # read-only, no execute = not listable
        yield d
        os.chmod(d, stat.S_IRWXU)  # restore so tmp_path cleanup works

    @pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses permission checks")
    def test_permission_denied_dir_does_not_raise(self, locked_dir, tmp_path):
        config = make_stratum_config(
            watch_dirs=[locked_dir],
            suggestions_dir=tmp_path,
        )
        result = _process_directory(config, dry_run=False)
        assert result.files_scanned == 0

    @pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses permission checks")
    def test_permission_denied_dir_writes_no_suggestions(self, locked_dir, tmp_path):
        config = make_stratum_config(
            watch_dirs=[locked_dir],
            suggestions_dir=tmp_path,
        )
        _process_directory(config, dry_run=False)
        log_file = tmp_path / "suggestions.jsonl"
        assert (
            not log_file.exists() or log_file.read_text(encoding="utf-8").strip() == ""
        )

    @pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses permission checks")
    def test_permission_denied_subdir_skips_that_subdir_only(self, tmp_path):
        """Files in accessible siblings of a locked subdir are still scanned."""
        accessible = tmp_path / "accessible"
        write_file(accessible / "file_a.txt", CONTENT_A)
        write_file(accessible / "file_b.txt", CONTENT_A)  # duplicate

        locked = tmp_path / "locked"
        locked.mkdir()
        write_file(locked / "secret.txt", CONTENT_A)
        os.chmod(locked, stat.S_IRUSR)

        try:
            config = make_stratum_config(
                watch_dirs=[accessible],
                suggestions_dir=tmp_path / "suggestions",
            )
            result = _process_directory(config, dry_run=False)
            assert result.files_scanned == 2
        finally:
            os.chmod(locked, stat.S_IRWXU)


@pytest.mark.integration
class TestPidAndDbCleanupOnFailure:
    def test_pid_is_removed_when_scan_raises_mid_run(self, tmp_path):
        """PID cleanup runs even when an unexpected error occurs during scanning."""
        config = make_stratum_config(
            watch_dirs=[tmp_path],
            suggestions_dir=tmp_path / "suggestions",
        )
        with patch(
            "stratum.main.scan", side_effect=RuntimeError("unexpected scan failure")
        ):
            with pytest.raises(RuntimeError, match="unexpected scan failure"):
                _run_stratum(config, dry_run=False)
        assert not _PID_PATH.exists()

    def test_db_is_removed_when_scan_raises_mid_run(self, tmp_path):
        config = make_stratum_config(
            watch_dirs=[tmp_path],
            suggestions_dir=tmp_path / "suggestions",
        )
        with patch(
            "stratum.main.scan", side_effect=RuntimeError("unexpected scan failure")
        ):
            with pytest.raises(RuntimeError):
                _run_stratum(config, dry_run=False)
        assert not _DB_PATH.exists()


@pytest.mark.integration
class TestSuggestionsLogFailure:
    def test_suggest_outside_context_raises_called_outside_context_manager(
        self, tmp_path
    ):
        from stratum.models import SuggestionAction, SuggestionEntry
        from datetime import datetime, timezone

        logger = SuggestionLogger(tmp_path)
        entry = SuggestionEntry(
            ts=datetime.now(timezone.utc),
            action=SuggestionAction.DELETE_DUPLICATE,
            path=tmp_path / "some_file.txt",
            reason="duplicate of other_file.txt",
            size_bytes=1024,
        )
        with pytest.raises(CalledOutsideContextManager):
            logger.suggest(entry)

    def test_suggestions_dir_is_a_file_raises_on_enter(self, tmp_path):
        """SuggestionLogger.__enter__ raises when log_path is an existing file."""
        fake_dir = tmp_path / "not_a_dir.txt"
        fake_dir.write_text("I am a file, not a directory")
        logger = SuggestionLogger(fake_dir)
        with pytest.raises(Exception):
            logger.__enter__()


@pytest.mark.integration
class TestIndexDeletionGuardrails:
    def test_del_db_with_none_path_raises_path_required(self, tmp_path):
        db_path = tmp_path / "test.db"
        with StratumIndex(db_path=db_path) as db:
            with pytest.raises(PathRequiredToDeleteDBException):
                db.del_db(path=None)

    def test_del_db_with_wrong_path_raises_deletion_path_incorrect(self, tmp_path):
        db_path = tmp_path / "test.db"
        wrong_path = tmp_path / "wrong.db"
        with StratumIndex(db_path=db_path) as db:
            with pytest.raises(DeletionPathIncorrectException):
                db.del_db(path=wrong_path)

    def test_del_db_with_correct_path_removes_file(self, tmp_path):
        db_path = tmp_path / "test.db"
        with StratumIndex(db_path=db_path) as db:
            assert db_path.exists()
            db.del_db(path=db_path)
        assert not db_path.exists()


@pytest.mark.integration
class TestFileDisappearsBeforeHash:
    def test_file_deleted_between_scan_and_hash_raises(self, tmp_path):
        """If a file vanishes after scanning but before hashing, FileNotFoundError propagates."""
        write_file(tmp_path / "vanishing.txt", CONTENT_A)

        original_hash_file = _main_module.hash_file

        def hash_and_delete(path):
            path.unlink()
            return original_hash_file(path)

        config = make_stratum_config(
            watch_dirs=[tmp_path],
            suggestions_dir=tmp_path / "suggestions",
        )
        with patch("stratum.main.hash_file", side_effect=hash_and_delete):
            with pytest.raises(FileNotFoundError):
                _process_directory(config, dry_run=False)
