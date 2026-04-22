"""Unit tests for stratum.models domain types."""

from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from stratum.models import (
    FileRecord,
    FileType,
    SuggestionAction,
    SuggestionEntry,
    UploadConfig,
    UploadMode,
    UploadResult,
)

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
        assert record.file_type is None
        assert record.is_duplicate is None
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
        assert data["file_type"] is None


class TestFileRecordIsComplete:
    def test_returns_true_when_all_fields_set(self):
        record = make_file_record(
            content_hash="sha256abc",
            file_type=FileType.DOCUMENT,
            is_duplicate=False,
        )
        assert record.is_complete()

    def test_returns_true_when_is_duplicate_is_true(self):
        record = make_file_record(
            content_hash="sha256abc",
            file_type=FileType.CODE,
            is_duplicate=True,
        )
        assert record.is_complete()

    def test_returns_false_when_no_fields_set(self):
        record = make_file_record()
        assert not record.is_complete()

    def test_returns_false_when_content_hash_missing(self):
        record = make_file_record(file_type=FileType.DOCUMENT, is_duplicate=False)
        assert not record.is_complete()

    def test_returns_false_when_file_type_missing(self):
        record = make_file_record(content_hash="sha256abc", is_duplicate=False)
        assert not record.is_complete()

    def test_returns_false_when_is_duplicate_is_none(self):
        record = make_file_record(content_hash="sha256abc", file_type=FileType.DOCUMENT)
        assert not record.is_complete()

    def test_returns_false_when_content_hash_is_empty_string(self):
        record = make_file_record(
            content_hash="", file_type=FileType.CODE, is_duplicate=False
        )
        assert not record.is_complete()


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


# ---------------------------------------------------------------------------
# UploadMode
# ---------------------------------------------------------------------------


class TestUploadMode:
    def test_metadata_only_is_importable(self):
        assert UploadMode.METADATA_ONLY == "METADATA_ONLY"

    def test_full_content_is_importable(self):
        assert UploadMode.FULL_CONTENT == "FULL_CONTENT"

    def test_is_str_enum(self):
        assert isinstance(UploadMode.METADATA_ONLY, str)


# ---------------------------------------------------------------------------
# UploadConfig
# ---------------------------------------------------------------------------


class TestUploadConfig:
    def test_valid_construction_with_all_fields(self):
        cfg = UploadConfig(
            mode=UploadMode.METADATA_ONLY,
            bucket="my-bucket",
            prefix="stratum/",
            region="us-east-1",
            profile="stratum",
        )
        assert cfg.mode == UploadMode.METADATA_ONLY
        assert cfg.bucket == "my-bucket"
        assert cfg.prefix == "stratum/"
        assert cfg.region == "us-east-1"
        assert cfg.profile == "stratum"

    def test_default_mode_is_metadata_only(self):
        cfg = UploadConfig()
        assert cfg.mode == UploadMode.METADATA_ONLY

    def test_default_prefix(self):
        cfg = UploadConfig()
        assert cfg.prefix == "stratum/"

    def test_profile_can_be_none(self):
        cfg = UploadConfig(bucket="b", region="us-east-1", profile=None)
        assert cfg.profile is None

    def test_bucket_can_be_empty_string(self):
        cfg = UploadConfig()
        assert cfg.bucket == ""

    def test_full_content_mode_accepted_at_config_time(self):
        cfg = UploadConfig(mode=UploadMode.FULL_CONTENT)
        assert cfg.mode == UploadMode.FULL_CONTENT


# ---------------------------------------------------------------------------
# UploadResult
# ---------------------------------------------------------------------------


def make_upload_result(**kwargs) -> UploadResult:
    defaults = dict(s3_key="stratum/meta/2024/03/abc123.json", bytes_transferred=400)
    defaults.update(kwargs)
    return UploadResult(**defaults)


class TestUploadResult:
    def test_valid_success_result(self):
        result = make_upload_result()
        assert result.s3_key == "stratum/meta/2024/03/abc123.json"
        assert result.bytes_transferred == 400

    def test_frozen_mutation_raises(self):
        result = make_upload_result()
        with pytest.raises(ValidationError):
            result.success = False

    def test_missing_s3_key_raises(self):
        with pytest.raises(ValidationError):
            UploadResult(bytes_transferred=400)


# ---------------------------------------------------------------------------
# FileRecord — upload_result field and frozen copy pattern
# ---------------------------------------------------------------------------


class TestFileRecordUploadResult:
    def test_upload_result_defaults_to_none(self):
        record = make_file_record()
        assert record.upload_result is None

    def test_model_copy_attaches_upload_result(self):
        record = make_file_record()
        result = make_upload_result()
        updated = record.model_copy(update={"upload_result": result})
        assert updated.upload_result == result

    def test_model_copy_returns_new_instance(self):
        record = make_file_record()
        result = make_upload_result()
        updated = record.model_copy(update={"upload_result": result})
        assert updated is not record

    def test_original_record_unchanged_after_copy(self):
        record = make_file_record()
        result = make_upload_result()
        record.model_copy(update={"upload_result": result})
        assert record.upload_result is None

    def test_copied_record_is_still_frozen(self):
        record = make_file_record()
        result = make_upload_result()
        updated = record.model_copy(update={"upload_result": result})
        with pytest.raises(ValidationError):
            updated.size_bytes = 9999
