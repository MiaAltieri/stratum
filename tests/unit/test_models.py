"""Unit tests for stratum.models domain types."""

from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from stratum.models import FileRecord, FileType, SuggestionAction, SuggestionEntry

DT = datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc)


def make_file_record(**kwargs) -> FileRecord:
    defaults = dict(
        path=Path("/some/file.txt"),
        size_bytes=1024,
        mtime=DT,
        atime=DT,
    )
    defaults.update(kwargs)
    return FileRecord(**defaults)


class TestFileRecord:
    def test_valid_construction(self):
        record = make_file_record()
        assert record.path == Path("/some/file.txt")
        assert record.size_bytes == 1024
        assert record.mtime == DT
        assert record.file_type == FileType.OTHER
        assert record.is_duplicate is False
        assert record.content_hash is None
        assert record.duplicate_of is None

    def test_frozen_mutation_raises(self):
        record = make_file_record()
        with pytest.raises(ValidationError):
            record.size_bytes = 9999

    def test_year_month_output(self):
        record = make_file_record(mtime=datetime(2023, 7, 4, tzinfo=timezone.utc))
        assert record.year_month == "2023/07"

    def test_year_month_included_in_model_dump(self):
        record = make_file_record(mtime=datetime(2024, 11, 1, tzinfo=timezone.utc))
        data = record.model_dump()
        assert data["year_month"] == "2024/11"

    def test_enum_serialisation_via_model_dump(self):
        record = make_file_record(file_type=FileType.CODE)
        data = record.model_dump()
        assert data["file_type"] == "code"

    def test_enum_serialisation_defaults_other(self):
        record = make_file_record()
        data = record.model_dump()
        assert data["file_type"] == "other"


class TestSuggestionEntry:
    def make_entry(self, **kwargs) -> SuggestionEntry:
        defaults = dict(
            ts=DT,
            action=SuggestionAction.DELETE_DUPLICATE,
            path=Path("/some/file.txt"),
            reason="exact duplicate",
            size_bytes=512,
        )
        defaults.update(kwargs)
        return SuggestionEntry(**defaults)

    def test_valid_construction(self):
        entry = self.make_entry()
        assert entry.action == SuggestionAction.DELETE_DUPLICATE
        assert entry.reason == "exact duplicate"
        assert entry.extra == {}

    def test_frozen_mutation_raises(self):
        entry = self.make_entry()
        with pytest.raises(ValidationError):
            entry.reason = "changed"

    def test_enum_serialisation_via_model_dump(self):
        entry = self.make_entry(action=SuggestionAction.ARCHIVE_CANDIDATE)
        data = entry.model_dump()
        assert data["action"] == "ARCHIVE_CANDIDATE"
