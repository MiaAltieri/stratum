"""Unit tests for stratum.suggestion_log — JSONL suggestion logger (STRAT-108)."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from stratum.models import FileRecord, SuggestionAction, SuggestionEntry
from stratum.suggestion_log import CalledOutsideContextManager, SuggestionLogger

SUGGESTION_FILE_NAME = "suggestions.jsonl"

DT = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def make_entry(**kwargs) -> SuggestionEntry:
    defaults = dict(
        ts=DT,
        action=SuggestionAction.DELETE_DUPLICATE,
        path=Path("/some/file.txt"),
        reason="exact duplicate",
        size_bytes=1024,
    )
    defaults.update(kwargs)
    return SuggestionEntry(**defaults)


def make_file_record(**kwargs) -> FileRecord:
    defaults = dict(
        path=Path("/some/file.txt"),
        size_bytes=2048,
        mtime=DT,
        atime=DT,
        content_hash="a" * 64,
    )
    defaults.update(kwargs)
    return FileRecord(**defaults)


def log_file(log_path: Path) -> Path:
    return log_path / SUGGESTION_FILE_NAME


# ---------------------------------------------------------------------------
# Context manager behaviour
# ---------------------------------------------------------------------------


class TestContextManager:
    def test_enters_and_exits_cleanly(self, tmp_path):
        with SuggestionLogger(log_path=tmp_path) as logger:
            assert logger is not None

    def test_suggestions_file_created_on_enter(self, tmp_path):
        with SuggestionLogger(log_path=tmp_path) as logger:
            logger.suggest(make_entry())
        assert log_file(tmp_path).exists()

    def test_file_closed_after_exit(self, tmp_path):
        with SuggestionLogger(log_path=tmp_path) as logger:
            f = logger._file_conn

        assert f.closed

    def test_file_closed_on_exception(self, tmp_path):
        f_ref = None
        with pytest.raises(RuntimeError):
            with SuggestionLogger(log_path=tmp_path) as logger:
                f_ref = logger._file_conn
                raise RuntimeError("boom")

        assert f_ref.closed

    def test_parent_dirs_created_if_missing(self, tmp_path):
        nested = tmp_path / "deep" / "nested" / "logs"
        assert not nested.exists()
        with SuggestionLogger(log_path=nested):
            pass
        assert nested.exists()


# ---------------------------------------------------------------------------
# suggest() — line count and content
# ---------------------------------------------------------------------------


class TestSuggest:
    def test_single_suggest_writes_one_line(self, tmp_path):
        with SuggestionLogger(log_path=tmp_path) as logger:
            logger.suggest(make_entry())

        lines = log_file(tmp_path).read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1

    def test_multiple_suggests_each_write_one_line(self, tmp_path):
        entries = [
            make_entry(reason="first"),
            make_entry(action=SuggestionAction.ARCHIVE_CANDIDATE, reason="second"),
            make_entry(action=SuggestionAction.LARGE_FILE_ALERT, reason="third"),
        ]
        with SuggestionLogger(log_path=tmp_path) as logger:
            for entry in entries:
                logger.suggest(entry)

        lines = log_file(tmp_path).read_text(encoding="utf-8").splitlines()
        assert len(lines) == 3

    def test_each_line_ends_with_newline(self, tmp_path):
        with SuggestionLogger(log_path=tmp_path) as logger:
            logger.suggest(make_entry())

        raw = log_file(tmp_path).read_bytes()
        assert raw.endswith(b"\n")


# ---------------------------------------------------------------------------
# Append behaviour — second session adds to existing file
# ---------------------------------------------------------------------------


class TestAppendMode:
    def test_second_session_appends_not_overwrites(self, tmp_path):
        entry_a = make_entry(reason="first session")
        entry_b = make_entry(reason="second session")

        with SuggestionLogger(log_path=tmp_path) as logger:
            logger.suggest(entry_a)

        with SuggestionLogger(log_path=tmp_path) as logger:
            logger.suggest(entry_b)

        lines = log_file(tmp_path).read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2

    def test_second_session_preserves_first_entry(self, tmp_path):
        entry_a = make_entry(reason="preserved")
        entry_b = make_entry(reason="new")

        with SuggestionLogger(log_path=tmp_path) as logger:
            logger.suggest(entry_a)

        with SuggestionLogger(log_path=tmp_path) as logger:
            logger.suggest(entry_b)

        lines = log_file(tmp_path).read_text(encoding="utf-8").splitlines()
        first = json.loads(lines[0])
        assert first["reason"] == "preserved"


# ---------------------------------------------------------------------------
# Valid JSONL output
# ---------------------------------------------------------------------------


class TestJsonlOutput:
    def test_each_line_is_valid_json(self, tmp_path):
        with SuggestionLogger(log_path=tmp_path) as logger:
            logger.suggest(make_entry())
            logger.suggest(make_entry(action=SuggestionAction.REORGANIZE))

        lines = log_file(tmp_path).read_text(encoding="utf-8").splitlines()
        for line in lines:
            json.loads(line)  # must not raise

    def test_all_suggestion_entry_fields_present(self, tmp_path):
        with SuggestionLogger(log_path=tmp_path) as logger:
            logger.suggest(make_entry(extra={"key": "val"}))

        line = log_file(tmp_path).read_text(encoding="utf-8").splitlines()[0]
        data = json.loads(line)

        assert "ts" in data
        assert "action" in data
        assert "path" in data
        assert "reason" in data
        assert "size_bytes" in data
        assert "extra" in data

    def test_line_deserialises_to_valid_suggestion_entry(self, tmp_path):
        original = make_entry(reason="round-trip check", size_bytes=512)
        with SuggestionLogger(log_path=tmp_path) as logger:
            logger.suggest(original)

        line = log_file(tmp_path).read_text(encoding="utf-8").splitlines()[0]
        restored = SuggestionEntry.model_validate_json(line)

        assert restored.reason == "round-trip check"
        assert restored.size_bytes == 512
        assert restored.action == SuggestionAction.DELETE_DUPLICATE

    def test_action_value_serialised_as_string(self, tmp_path):
        with SuggestionLogger(log_path=tmp_path) as logger:
            logger.suggest(make_entry(action=SuggestionAction.ARCHIVE_CANDIDATE))

        line = log_file(tmp_path).read_text(encoding="utf-8").splitlines()[0]
        data = json.loads(line)
        assert data["action"] == "ARCHIVE_CANDIDATE"

    def test_extra_dict_preserved_in_output(self, tmp_path):
        with SuggestionLogger(log_path=tmp_path) as logger:
            logger.suggest(make_entry(extra={"original_path": "/other/file.txt"}))

        line = log_file(tmp_path).read_text(encoding="utf-8").splitlines()[0]
        data = json.loads(line)
        assert data["extra"] == {"original_path": "/other/file.txt"}


# ---------------------------------------------------------------------------
# suggest() outside context manager raises CalledOutsideContextManager
# ---------------------------------------------------------------------------


class TestCalledOutsideContextManager:
    def test_suggest_before_enter_raises(self, tmp_path):
        logger = SuggestionLogger(log_path=tmp_path)
        with pytest.raises(CalledOutsideContextManager):
            logger.suggest(make_entry())

    def test_suggest_after_exit_raises(self, tmp_path):
        with SuggestionLogger(log_path=tmp_path) as logger:
            pass  # exits here, _file_conn is closed

        with pytest.raises(CalledOutsideContextManager):
            logger.suggest(make_entry())


# ---------------------------------------------------------------------------
# SuggestionEntry.for_duplicate factory (classmethod on model)
# ---------------------------------------------------------------------------


class TestForDuplicateFactory:
    def test_for_duplicate_returns_suggestion_entry(self):
        record = make_file_record()
        original = Path("/original/file.txt")
        entry = SuggestionEntry.for_duplicate(record, original)
        assert isinstance(entry, SuggestionEntry)

    def test_for_duplicate_action_is_delete_duplicate(self):
        record = make_file_record()
        entry = SuggestionEntry.for_duplicate(record, Path("/orig/file.txt"))
        assert entry.action == SuggestionAction.DELETE_DUPLICATE

    def test_for_duplicate_extra_contains_original_path(self):
        record = make_file_record()
        original = Path("/orig/file.txt")
        entry = SuggestionEntry.for_duplicate(record, original)
        assert entry.extra["original_path"] == str(original)

    def test_for_duplicate_size_matches_record(self):
        record = make_file_record(size_bytes=99_999)
        entry = SuggestionEntry.for_duplicate(record, Path("/orig/x"))
        assert entry.size_bytes == 99_999

    def test_for_duplicate_written_to_log(self, tmp_path):
        record = make_file_record()
        original = Path("/orig/master.txt")
        entry = SuggestionEntry.for_duplicate(record, original)

        with SuggestionLogger(log_path=tmp_path) as logger:
            logger.suggest(entry)

        line = log_file(tmp_path).read_text(encoding="utf-8").splitlines()[0]
        restored = SuggestionEntry.model_validate_json(line)
        assert restored.action == SuggestionAction.DELETE_DUPLICATE
        assert restored.extra["original_path"] == str(original)
