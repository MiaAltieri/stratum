"""Domain models for Stratum — shared types used across all modules."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, computed_field


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


class FileRecord(BaseModel):
    """Keeps track of a files generating a frozen record."""

    model_config = ConfigDict(frozen=True)
    path: Path
    size_bytes: int
    mtime: datetime
    atime: datetime
    content_hash: str | None = None  # set by hasher
    file_type: FileType = FileType.OTHER  # set by tagger
    is_duplicate: bool = False
    duplicate_of: Path | None = None

    @computed_field  # type: ignore[misc]
    @property
    def year_month(self) -> str:
        return self.mtime.strftime("%Y/%m")


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
