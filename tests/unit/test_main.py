"""Unit tests for stratum.main — orchestrator and CLI entry point (STRAT-109)."""

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from stratum.main import (
    PID_FILE_NAME,
    _delete_pid,
    _parse_args,
    _process_directory,
    _run_stratum,
    _write_pid,
    run,
)
from stratum.models import FileRecord, FileType, ScanMetadata, SuggestionAction

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

DT = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def make_file_record(**kwargs) -> FileRecord:
    """Construct a minimal FileRecord for testing."""
    defaults = dict(
        path=Path("/fake/dir/file.txt"),
        size_bytes=1024,
        mtime=DT,
        atime=DT,
    )
    defaults.update(kwargs)
    return FileRecord(**defaults)


def make_mock_config(dedup_enabled: bool = True, log_path: Path = Path("/fake/.stratum/")):
    """Return a minimal mock StratumConfig."""
    cfg = MagicMock()
    cfg.scan = MagicMock()
    cfg.suggestions.log_path = log_path
    cfg.suggestions.dedup_enabled = dedup_enabled
    return cfg


def make_mock_index(contains_return=None) -> MagicMock:
    """Return a MagicMock StratumIndex that acts as a context manager."""
    mock_index = MagicMock()
    mock_index.__enter__ = MagicMock(return_value=mock_index)
    mock_index.__exit__ = MagicMock(return_value=False)
    mock_index.contains.return_value = contains_return
    return mock_index


def make_mock_logger() -> MagicMock:
    """Return a MagicMock SuggestionLogger that acts as a context manager."""
    mock_log = MagicMock()
    mock_log.__enter__ = MagicMock(return_value=mock_log)
    mock_log.__exit__ = MagicMock(return_value=False)
    return mock_log


# ---------------------------------------------------------------------------
# _parse_args
# ---------------------------------------------------------------------------


class TestParseArgs:
    def test_default_config_path(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["stratum"])
        args = _parse_args()
        assert args.config_path == Path("~/.stratum/stratum.toml")

    def test_custom_config_path(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["stratum", "--config_path", "/custom/config.toml"])
        args = _parse_args()
        assert args.config_path == Path("/custom/config.toml")

    def test_default_dry_run_is_true(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["stratum"])
        args = _parse_args()
        assert args.dry_run is True

    def test_config_path_is_path_type(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["stratum", "--config_path", "/some/path.toml"])
        args = _parse_args()
        assert isinstance(args.config_path, Path)

    def test_dry_run_explicit_true(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["stratum", "--dry_run", "True"])
        args = _parse_args()
        # argparse type=bool: bool("True") == True
        assert args.dry_run is True


# ---------------------------------------------------------------------------
# _write_pid
# ---------------------------------------------------------------------------


class TestWritePid:
    def test_writes_current_pid_to_file(self):
        m = mock_open()
        with (
            patch("builtins.open", m),
            patch("stratum.main.os.getpid", return_value=99999),
            patch.object(Path, "mkdir"),
        ):
            _write_pid()
        m().write.assert_called_once_with("99999")

    def test_opens_file_in_write_mode(self):
        m = mock_open()
        with (
            patch("builtins.open", m),
            patch("stratum.main.os.getpid", return_value=1),
            patch.object(Path, "mkdir"),
        ):
            _write_pid()
        assert m.call_args[0][1] == "w"

    def test_pid_file_has_correct_filename(self):
        m = mock_open()
        with (
            patch("builtins.open", m),
            patch("stratum.main.os.getpid", return_value=1),
            patch.object(Path, "mkdir"),
        ):
            _write_pid()
        opened_path = m.call_args[0][0]
        assert opened_path.name == PID_FILE_NAME

    def test_pid_written_as_string(self):
        m = mock_open()
        with (
            patch("builtins.open", m),
            patch("stratum.main.os.getpid", return_value=42),
            patch.object(Path, "mkdir"),
        ):
            _write_pid()
        written = m().write.call_args[0][0]
        assert isinstance(written, str)
        assert written == "42"


# ---------------------------------------------------------------------------
# _delete_pid
# ---------------------------------------------------------------------------


class TestDeletePid:
    def test_removes_pid_file_when_present(self):
        with (
            patch("stratum.main.os.path.exists", return_value=True),
            patch("stratum.main.os.remove") as mock_remove,
        ):
            _delete_pid()
        mock_remove.assert_called_once()

    def test_does_not_remove_when_file_missing(self):
        with (
            patch("stratum.main.os.path.exists", return_value=False),
            patch("stratum.main.os.remove") as mock_remove,
        ):
            _delete_pid()
        mock_remove.assert_not_called()

    def test_removed_path_contains_pid_filename(self):
        with (
            patch("stratum.main.os.path.exists", return_value=True),
            patch("stratum.main.os.remove") as mock_remove,
        ):
            _delete_pid()
        removed_path = mock_remove.call_args[0][0]
        assert PID_FILE_NAME in str(removed_path)

    def test_no_exception_when_file_missing(self):
        with (
            patch("stratum.main.os.path.exists", return_value=False),
            patch("stratum.main.os.remove"),
        ):
            _delete_pid()  # must not raise


# ---------------------------------------------------------------------------
# _process_directory — empty scan
# ---------------------------------------------------------------------------


class TestProcessDirectoryEmptyScan:
    def _run_empty(self):
        cfg = make_mock_config()
        with (
            patch("stratum.main.scan", return_value=[]),
            patch("stratum.main.StratumIndex", return_value=make_mock_index()),
            patch("stratum.main.SuggestionLogger", return_value=make_mock_logger()),
        ):
            return _process_directory(cfg, dry_run=False)

    def test_returns_scan_metadata_instance(self):
        assert isinstance(self._run_empty(), ScanMetadata)

    def test_files_scanned_is_zero(self):
        assert self._run_empty().files_scanned == 0

    def test_duplicates_found_is_zero(self):
        assert self._run_empty().duplicates_found == 0

    def test_suggestions_written_is_zero(self):
        assert self._run_empty().suggestions_written == 0

    def test_duration_seconds_is_non_negative(self):
        assert self._run_empty().duration_seconds >= 0

    def test_duration_seconds_is_integer(self):
        assert isinstance(self._run_empty().duration_seconds, int)


# ---------------------------------------------------------------------------
# _process_directory — file counts
# ---------------------------------------------------------------------------


class TestProcessDirectoryCounts:
    def test_scanned_count_matches_number_of_files(self):
        cfg = make_mock_config()
        records = [make_file_record(path=Path(f"/dir/file_{i}.txt")) for i in range(4)]
        with (
            patch("stratum.main.scan", return_value=records),
            patch("stratum.main.hash_file", return_value="h"),
            patch("stratum.main.classify", return_value=FileType.OTHER),
            patch(
                "stratum.main.StratumIndex",
                return_value=make_mock_index(contains_return=None),
            ),
            patch("stratum.main.SuggestionLogger", return_value=make_mock_logger()),
        ):
            result = _process_directory(cfg, dry_run=False)

        assert result.files_scanned == 4

    def test_hash_file_called_once_per_record(self):
        cfg = make_mock_config()
        records = [make_file_record(path=Path(f"/dir/file_{i}.txt")) for i in range(3)]
        with (
            patch("stratum.main.scan", return_value=records),
            patch("stratum.main.hash_file", return_value="h") as mock_hash,
            patch("stratum.main.classify", return_value=FileType.OTHER),
            patch("stratum.main.StratumIndex", return_value=make_mock_index()),
            patch("stratum.main.SuggestionLogger", return_value=make_mock_logger()),
        ):
            _process_directory(cfg, dry_run=False)

        assert mock_hash.call_count == 3

    def test_classify_called_once_per_record(self):
        cfg = make_mock_config()
        records = [make_file_record(path=Path(f"/dir/file_{i}.txt")) for i in range(2)]
        with (
            patch("stratum.main.scan", return_value=records),
            patch("stratum.main.hash_file", return_value="h"),
            patch("stratum.main.classify", return_value=FileType.DOCUMENT) as mock_classify,
            patch("stratum.main.StratumIndex", return_value=make_mock_index()),
            patch("stratum.main.SuggestionLogger", return_value=make_mock_logger()),
        ):
            _process_directory(cfg, dry_run=False)

        assert mock_classify.call_count == 2


# ---------------------------------------------------------------------------
# _process_directory — duplicate detection
# ---------------------------------------------------------------------------


class TestProcessDirectoryDuplicateDetection:
    def test_same_path_in_index_is_not_flagged_as_duplicate(self):
        """contains() returning the current file's own path means it's already indexed."""
        cfg = make_mock_config()
        path = Path("/dir/file.txt")
        record = make_file_record(path=path)
        mock_index = make_mock_index(contains_return=str(path))
        mock_log = make_mock_logger()

        with (
            patch("stratum.main.scan", return_value=[record]),
            patch("stratum.main.hash_file", return_value="abc"),
            patch("stratum.main.classify", return_value=FileType.OTHER),
            patch("stratum.main.StratumIndex", return_value=mock_index),
            patch("stratum.main.SuggestionLogger", return_value=mock_log),
        ):
            result = _process_directory(cfg, dry_run=False)

        mock_log.suggest.assert_not_called()
        assert result.duplicates_found == 0
        assert result.suggestions_written == 0

    def test_different_path_in_index_creates_suggestion_entry(self):
        """contains() returning a different path → DELETE_DUPLICATE suggestion is emitted."""
        cfg = make_mock_config()
        record = make_file_record(path=Path("/dir/copy.txt"))
        mock_index = make_mock_index(contains_return="/dir/original.txt")
        mock_log = make_mock_logger()

        with (
            patch("stratum.main.scan", return_value=[record]),
            patch("stratum.main.hash_file", return_value="abc"),
            patch("stratum.main.classify", return_value=FileType.OTHER),
            patch("stratum.main.StratumIndex", return_value=mock_index),
            patch("stratum.main.SuggestionLogger", return_value=mock_log),
        ):
            result = _process_directory(cfg, dry_run=False)

        mock_log.suggest.assert_called_once()
        assert result.duplicates_found == 1
        assert result.suggestions_written == 1

    def test_suggestion_action_is_delete_duplicate(self):
        cfg = make_mock_config()
        record = make_file_record(path=Path("/dir/copy.txt"))
        with (
            patch("stratum.main.scan", return_value=[record]),
            patch("stratum.main.hash_file", return_value="abc"),
            patch("stratum.main.classify", return_value=FileType.OTHER),
            patch(
                "stratum.main.StratumIndex",
                return_value=make_mock_index(contains_return="/dir/orig.txt"),
            ),
            patch(
                "stratum.main.SuggestionLogger",
                return_value=(mock_log := make_mock_logger()),
            ),
        ):
            _process_directory(cfg, dry_run=False)

        entry = mock_log.suggest.call_args[0][0]
        assert entry.action == SuggestionAction.DELETE_DUPLICATE

    def test_suggestion_path_matches_current_file(self):
        cfg = make_mock_config()
        expected_path = Path("/dir/copy.txt")
        record = make_file_record(path=expected_path)
        with (
            patch("stratum.main.scan", return_value=[record]),
            patch("stratum.main.hash_file", return_value="abc"),
            patch("stratum.main.classify", return_value=FileType.OTHER),
            patch(
                "stratum.main.StratumIndex",
                return_value=make_mock_index(contains_return="/dir/orig.txt"),
            ),
            patch(
                "stratum.main.SuggestionLogger",
                return_value=(mock_log := make_mock_logger()),
            ),
        ):
            _process_directory(cfg, dry_run=False)

        entry = mock_log.suggest.call_args[0][0]
        assert entry.path == expected_path

    def test_suggestion_size_bytes_matches_record(self):
        cfg = make_mock_config()
        record = make_file_record(path=Path("/dir/copy.txt"), size_bytes=8192)
        with (
            patch("stratum.main.scan", return_value=[record]),
            patch("stratum.main.hash_file", return_value="abc"),
            patch("stratum.main.classify", return_value=FileType.OTHER),
            patch(
                "stratum.main.StratumIndex",
                return_value=make_mock_index(contains_return="/dir/orig.txt"),
            ),
            patch(
                "stratum.main.SuggestionLogger",
                return_value=(mock_log := make_mock_logger()),
            ),
        ):
            _process_directory(cfg, dry_run=False)

        entry = mock_log.suggest.call_args[0][0]
        assert entry.size_bytes == 8192

    def test_suggestion_reason_references_original_path(self):
        cfg = make_mock_config()
        original = "/dir/original.txt"
        record = make_file_record(path=Path("/dir/copy.txt"))
        with (
            patch("stratum.main.scan", return_value=[record]),
            patch("stratum.main.hash_file", return_value="abc"),
            patch("stratum.main.classify", return_value=FileType.OTHER),
            patch(
                "stratum.main.StratumIndex",
                return_value=make_mock_index(contains_return=original),
            ),
            patch(
                "stratum.main.SuggestionLogger",
                return_value=(mock_log := make_mock_logger()),
            ),
        ):
            _process_directory(cfg, dry_run=False)

        entry = mock_log.suggest.call_args[0][0]
        assert original in entry.reason

    def test_multiple_duplicates_each_produce_suggestion(self):
        cfg = make_mock_config()
        records = [make_file_record(path=Path(f"/dir/copy_{i}.txt")) for i in range(3)]
        mock_log = make_mock_logger()
        with (
            patch("stratum.main.scan", return_value=records),
            patch("stratum.main.hash_file", return_value="same_hash"),
            patch("stratum.main.classify", return_value=FileType.OTHER),
            patch(
                "stratum.main.StratumIndex",
                return_value=make_mock_index(contains_return="/dir/orig.txt"),
            ),
            patch("stratum.main.SuggestionLogger", return_value=mock_log),
        ):
            result = _process_directory(cfg, dry_run=False)

        assert mock_log.suggest.call_count == 3
        assert result.duplicates_found == 3
        assert result.suggestions_written == 3

    def test_suggestion_entry_has_timestamp(self):
        cfg = make_mock_config()
        record = make_file_record(path=Path("/dir/copy.txt"))
        with (
            patch("stratum.main.scan", return_value=[record]),
            patch("stratum.main.hash_file", return_value="abc"),
            patch("stratum.main.classify", return_value=FileType.OTHER),
            patch(
                "stratum.main.StratumIndex",
                return_value=make_mock_index(contains_return="/dir/orig.txt"),
            ),
            patch(
                "stratum.main.SuggestionLogger",
                return_value=(mock_log := make_mock_logger()),
            ),
        ):
            _process_directory(cfg, dry_run=False)

        entry = mock_log.suggest.call_args[0][0]
        assert entry.ts is not None


# ---------------------------------------------------------------------------
# _process_directory — dry_run flag
# ---------------------------------------------------------------------------


class TestProcessDirectoryDryRun:
    def test_dry_run_true_does_not_call_suggest(self):
        cfg = make_mock_config()
        record = make_file_record(path=Path("/dir/copy.txt"))
        mock_log = make_mock_logger()

        with (
            patch("stratum.main.scan", return_value=[record]),
            patch("stratum.main.hash_file", return_value="abc"),
            patch("stratum.main.classify", return_value=FileType.OTHER),
            patch(
                "stratum.main.StratumIndex",
                return_value=make_mock_index(contains_return="/dir/orig.txt"),
            ),
            patch("stratum.main.SuggestionLogger", return_value=mock_log),
        ):
            _process_directory(cfg, dry_run=True)

        mock_log.suggest.assert_not_called()

    def test_dry_run_true_prints_duplicate_paths(self, capsys):
        cfg = make_mock_config()
        record = make_file_record(path=Path("/dir/copy.txt"))
        with (
            patch("stratum.main.scan", return_value=[record]),
            patch("stratum.main.hash_file", return_value="abc"),
            patch("stratum.main.classify", return_value=FileType.OTHER),
            patch(
                "stratum.main.StratumIndex",
                return_value=make_mock_index(contains_return="/dir/orig.txt"),
            ),
            patch("stratum.main.SuggestionLogger", return_value=make_mock_logger()),
        ):
            _process_directory(cfg, dry_run=True)

        out = capsys.readouterr().out
        assert "/dir/copy.txt" in out

    def test_dry_run_false_calls_suggest(self):
        cfg = make_mock_config()
        record = make_file_record(path=Path("/dir/copy.txt"))
        mock_log = make_mock_logger()

        with (
            patch("stratum.main.scan", return_value=[record]),
            patch("stratum.main.hash_file", return_value="abc"),
            patch("stratum.main.classify", return_value=FileType.OTHER),
            patch(
                "stratum.main.StratumIndex",
                return_value=make_mock_index(contains_return="/dir/orig.txt"),
            ),
            patch("stratum.main.SuggestionLogger", return_value=mock_log),
        ):
            _process_directory(cfg, dry_run=False)

        mock_log.suggest.assert_called_once()

    def test_dry_run_does_not_affect_scanned_count(self):
        cfg = make_mock_config()
        records = [make_file_record(path=Path(f"/dir/f{i}.txt")) for i in range(5)]
        with (
            patch("stratum.main.scan", return_value=records),
            patch("stratum.main.hash_file", return_value="h"),
            patch("stratum.main.classify", return_value=FileType.OTHER),
            patch("stratum.main.StratumIndex", return_value=make_mock_index()),
            patch("stratum.main.SuggestionLogger", return_value=make_mock_logger()),
        ):
            result = _process_directory(cfg, dry_run=True)

        assert result.files_scanned == 5


# ---------------------------------------------------------------------------
# _run_stratum
# ---------------------------------------------------------------------------


class TestRunStratum:
    def test_pid_written_before_processing(self):
        cfg = make_mock_config()
        call_order = []

        def record_write():
            call_order.append("write")

        def record_process(*args, **kwargs):
            call_order.append("process")
            return MagicMock()

        with (
            patch("stratum.main._write_pid", side_effect=record_write),
            patch("stratum.main._delete_pid"),
            patch("stratum.main._process_directory", side_effect=record_process),
            patch("stratum.main.StratumIndex", return_value=make_mock_index()),
        ):
            _run_stratum(cfg, dry_run=False)

        assert call_order.index("write") < call_order.index("process")

    def test_pid_deleted_after_successful_run(self):
        cfg = make_mock_config()
        with (
            patch("stratum.main._write_pid"),
            patch("stratum.main._delete_pid") as mock_delete,
            patch("stratum.main._process_directory", return_value=MagicMock()),
            patch("stratum.main.StratumIndex", return_value=make_mock_index()),
        ):
            _run_stratum(cfg, dry_run=False)

        mock_delete.assert_called_once()

    def test_pid_deleted_even_when_exception_raised(self):
        cfg = make_mock_config()
        with (
            patch("stratum.main._write_pid"),
            patch("stratum.main._delete_pid") as mock_delete,
            patch("stratum.main._process_directory", side_effect=RuntimeError("boom")),
            patch("stratum.main.StratumIndex", return_value=make_mock_index()),
        ):
            with pytest.raises(RuntimeError):
                _run_stratum(cfg, dry_run=False)

        mock_delete.assert_called_once()

    def test_prints_summary_on_completion(self, capsys):
        cfg = make_mock_config()
        with (
            patch("stratum.main._write_pid"),
            patch("stratum.main._delete_pid"),
            patch("stratum.main._process_directory", return_value=MagicMock()),
            patch("stratum.main.StratumIndex", return_value=make_mock_index()),
        ):
            _run_stratum(cfg, dry_run=False)

        out = capsys.readouterr().out
        assert "Job complete" in out

    def test_passes_config_to_process_directory(self):
        cfg = make_mock_config()
        with (
            patch("stratum.main._write_pid"),
            patch("stratum.main._delete_pid"),
            patch("stratum.main._process_directory", return_value=MagicMock()) as mock_proc,
            patch("stratum.main.StratumIndex", return_value=make_mock_index()),
        ):
            _run_stratum(cfg, dry_run=False)

        assert mock_proc.call_args[0][0] is cfg

    def test_passes_dry_run_to_process_directory(self):
        cfg = make_mock_config()
        with (
            patch("stratum.main._write_pid"),
            patch("stratum.main._delete_pid"),
            patch("stratum.main._process_directory", return_value=MagicMock()) as mock_proc,
            patch("stratum.main.StratumIndex", return_value=make_mock_index()),
        ):
            _run_stratum(cfg, dry_run=True)

        assert mock_proc.call_args[0][1] is True


# ---------------------------------------------------------------------------
# _run_stratum — db cleanup
# ---------------------------------------------------------------------------


class TestRunStratumDbCleanup:
    def test_del_db_called_after_successful_run(self):
        cfg = make_mock_config()
        mock_index = make_mock_index()
        with (
            patch("stratum.main._write_pid"),
            patch("stratum.main._delete_pid"),
            patch("stratum.main._process_directory", return_value=MagicMock()),
            patch("stratum.main.StratumIndex", return_value=mock_index),
        ):
            _run_stratum(cfg, dry_run=False)

        mock_index.del_db.assert_called_once()

    def test_del_db_called_even_when_process_raises(self):
        cfg = make_mock_config()
        mock_index = make_mock_index()
        with (
            patch("stratum.main._write_pid"),
            patch("stratum.main._delete_pid"),
            patch("stratum.main._process_directory", side_effect=RuntimeError("boom")),
            patch("stratum.main.StratumIndex", return_value=mock_index),
        ):
            with pytest.raises(RuntimeError):
                _run_stratum(cfg, dry_run=False)

        mock_index.del_db.assert_called_once()

    def test_del_db_called_with_index_db_path(self):
        cfg = make_mock_config()
        mock_index = make_mock_index()
        with (
            patch("stratum.main._write_pid"),
            patch("stratum.main._delete_pid"),
            patch("stratum.main._process_directory", return_value=MagicMock()),
            patch("stratum.main.StratumIndex", return_value=mock_index),
        ):
            _run_stratum(cfg, dry_run=False)

        called_path = mock_index.del_db.call_args[1]["path"]
        assert called_path.name == "index.db"

    def test_del_db_path_is_inside_stratum_package(self):
        cfg = make_mock_config()
        mock_index = make_mock_index()
        with (
            patch("stratum.main._write_pid"),
            patch("stratum.main._delete_pid"),
            patch("stratum.main._process_directory", return_value=MagicMock()),
            patch("stratum.main.StratumIndex", return_value=mock_index),
        ):
            _run_stratum(cfg, dry_run=False)

        called_path = mock_index.del_db.call_args[1]["path"]
        assert "stratum" in str(called_path)


# ---------------------------------------------------------------------------
# _process_directory — record completeness
# ---------------------------------------------------------------------------


class TestProcessDirectoryRecordCompleteness:
    """Verify that each FileRecord is complete (is_complete() == True) after _process_directory."""

    def _run_and_capture_records(self, records, hash_val="sha256abc", file_type=FileType.DOCUMENT):
        """Run _process_directory and return the completed FileRecord objects."""
        completed = []
        original_model_copy = FileRecord.model_copy

        def capturing_model_copy(self_record, **kwargs):
            result = original_model_copy(self_record, **kwargs)
            completed.append(result)
            return result

        cfg = make_mock_config()
        with (
            patch("stratum.main.scan", return_value=records),
            patch("stratum.main.hash_file", return_value=hash_val),
            patch("stratum.main.classify", return_value=file_type),
            patch("stratum.main.StratumIndex", return_value=make_mock_index()),
            patch("stratum.main.SuggestionLogger", return_value=make_mock_logger()),
            patch.object(FileRecord, "model_copy", capturing_model_copy),
        ):
            _process_directory(cfg, dry_run=False)

        return completed

    def test_single_record_is_complete_after_processing(self):
        record = make_file_record(path=Path("/dir/file.txt"))
        completed = self._run_and_capture_records([record])
        assert len(completed) == 1
        assert completed[0].is_complete()

    def test_all_records_are_complete_when_multiple_files_scanned(self):
        records = [make_file_record(path=Path(f"/dir/file_{i}.txt")) for i in range(4)]
        completed = self._run_and_capture_records(records)
        assert all(r.is_complete() for r in completed)

    def test_completed_record_has_content_hash(self):
        record = make_file_record(path=Path("/dir/file.txt"))
        completed = self._run_and_capture_records([record], hash_val="deadbeef")
        assert completed[0].content_hash == "deadbeef"

    def test_completed_record_has_file_type(self):
        record = make_file_record(path=Path("/dir/file.txt"))
        completed = self._run_and_capture_records([record], file_type=FileType.CODE)
        assert completed[0].file_type == FileType.CODE

    def test_completed_record_has_is_duplicate_set(self):
        record = make_file_record(path=Path("/dir/file.txt"))
        completed = self._run_and_capture_records([record])
        assert completed[0].is_duplicate is not None

    def test_completed_record_is_not_duplicate_when_index_empty(self):
        record = make_file_record(path=Path("/dir/file.txt"))
        completed = self._run_and_capture_records([record])
        assert completed[0].is_duplicate is False

    def test_completed_record_is_duplicate_when_different_path_in_index(self):
        record = make_file_record(path=Path("/dir/copy.txt"))
        completed = []
        original_model_copy = FileRecord.model_copy

        def capturing_model_copy(self_record, **kwargs):
            result = original_model_copy(self_record, **kwargs)
            completed.append(result)
            return result

        cfg = make_mock_config()
        with (
            patch("stratum.main.scan", return_value=[record]),
            patch("stratum.main.hash_file", return_value="abc"),
            patch("stratum.main.classify", return_value=FileType.OTHER),
            patch(
                "stratum.main.StratumIndex",
                return_value=make_mock_index(contains_return="/dir/original.txt"),
            ),
            patch("stratum.main.SuggestionLogger", return_value=make_mock_logger()),
            patch.object(FileRecord, "model_copy", capturing_model_copy),
        ):
            _process_directory(cfg, dry_run=False)

        assert completed[0].is_complete()
        assert completed[0].is_duplicate is True


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


class TestRun:
    def test_calls_load_with_config_path_from_args(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["stratum", "--config_path", "/my/config.toml"])
        mock_cfg = make_mock_config()
        with (
            patch("stratum.main.load", return_value=mock_cfg) as mock_load,
            patch("stratum.main._run_stratum"),
        ):
            run()

        mock_load.assert_called_once_with(Path("/my/config.toml"))

    def test_calls_run_stratum_with_loaded_config(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["stratum"])
        mock_cfg = make_mock_config()
        with (
            patch("stratum.main.load", return_value=mock_cfg),
            patch("stratum.main._run_stratum") as mock_run,
        ):
            run()

        called_cfg = mock_run.call_args[0][0]
        assert called_cfg is mock_cfg

    def test_passes_dry_run_to_run_stratum(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["stratum"])
        with (
            patch("stratum.main.load", return_value=make_mock_config()),
            patch("stratum.main._run_stratum") as mock_run,
        ):
            run()

        dry_run_arg = mock_run.call_args[0][1]
        assert dry_run_arg is True

    def test_default_config_path_passed_to_load(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["stratum"])
        with (
            patch("stratum.main.load", return_value=make_mock_config()) as mock_load,
            patch("stratum.main._run_stratum"),
        ):
            run()

        loaded_path = mock_load.call_args[0][0]
        assert "stratum.toml" in str(loaded_path)
