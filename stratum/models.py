"""Domain models for Stratum — shared types used across all modules."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, computed_field, field_validator


class FileType(StrEnum):
    """Describes the file type."""

    DOCUMENT = "document"
    MEDIA = "media"
    ARCHIVE = "archive"
    CODE = "code"
    OTHER = "other"


class SuggestionAction(StrEnum):
    """Suggestions for file actions."""

    DELETE_DUPLICATE = "DELETE_DUPLICATE"
    ARCHIVE_CANDIDATE = "ARCHIVE_CANDIDATE"
    REORGANIZE = "REORGANIZE"
    LARGE_FILE_ALERT = "LARGE_FILE_ALERT"
    PERMISSION_ANOMALY = "PERMISSION_ANOMALY"


class UploadMode(StrEnum):
    """Upload modes for stratum."""

    METADATA_ONLY = "METADATA_ONLY"
    FULL_CONTENT = "FULL_CONTENT"  # forward-compatible; raises NotImplementedError in uploader


class PipelineConfig(BaseModel):
    """Controls the concurrency parameters for the Phase 3 upload pipeline."""

    upload_workers: int = 8
    queue_maxsize: int = 500

    @field_validator("upload_workers", mode="after")
    @classmethod
    def validate_upload_workers(cls, v: int) -> int:
        if v < 1:
            raise ValueError(f"upload_workers must be a positive integer, got {v}")
        return v

    @field_validator("queue_maxsize", mode="after")
    @classmethod
    def validate_queue_maxsize(cls, v: int) -> int:
        if v < 1:
            raise ValueError(f"queue_maxsize must be a positive integer, got {v}")
        return v


class UploadConfig(BaseModel):
    """Upload specifics for stratum."""

    mode: UploadMode = UploadMode.METADATA_ONLY
    bucket: str = ""
    prefix: str = "stratum/"
    region: str = ""
    profile: str | None = "stratum"


class UploadResult(BaseModel):
    """Upload metadata, one per FileRecord"""

    model_config = ConfigDict(frozen=True)
    s3_key: str
    bytes_transferred: int


class ScanMetadata(BaseModel):
    """History of scan."""

    files_scanned: int
    duplicates_found: int
    suggestions_written: int
    duration_seconds: int
    uploads: int
    failed_uploads: int


class FileRecord(BaseModel):
    """Keeps track of a files generating a frozen record."""

    model_config = ConfigDict(frozen=True)
    path: Path
    size_bytes: int
    mtime: datetime
    atime: datetime
    ext: str | None = None  # set by scanner TODO !!! where is this used
    content_hash: str | None = None  # set by hasher
    file_type: FileType | None = None  # set by tagger
    is_duplicate: bool | None = None  # set downstream in ?scan? module
    duplicate_of: Path | None = None  # set downstream in ?scan? module
    # set by the orchestra via model_copy (bc FileRecord is frozen)
    upload_result: UploadResult | None = None

    @computed_field  # type: ignore[misc]
    @property
    def year_month(self) -> str:
        return self.mtime.strftime("%Y/%m")

    def is_complete(self) -> bool:
        """Returns true if FileRecord has been processed and has complete fields."""
        return self.content_hash and self.file_type and (self.is_duplicate is not None)


class SuggestionEntry(BaseModel):
    """Suggestion for each file.

    Note: at this stage we don't actually modify files we only make suggestions.
    In the future we will actually change files so will eventually have that functionality
    """

    model_config = ConfigDict(frozen=True)
    ts: datetime
    action: SuggestionAction
    path: Path
    reason: str
    size_bytes: int
    extra: dict[str, str] = {}

    @classmethod
    def for_duplicate(cls, record: FileRecord, original_path: Path) -> SuggestionEntry:
        return cls(
            ts=datetime.now(),
            action=SuggestionAction.DELETE_DUPLICATE,
            path=str(record.path),
            reason=f"Duplicate of {original_path} (sha256: {record.content_hash})",
            size_bytes=record.size_bytes,
            extra={"original_path": str(original_path)},
        )
