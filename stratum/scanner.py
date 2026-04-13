"""File system scanner — walks directories and yields FileRecord objects."""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from posix import DirEntry
from typing import Iterator

from stratum.config import ScanConfig
from stratum.models import FileRecord

logger = logging.getLogger(__name__)

ONE_MB = 1024**2


def scan(config: ScanConfig) -> Iterator[FileRecord]:
    for dir in config.watch_dirs:
        yield from _walk(dir, config, depth=0)


def _walk(directory: Path, config: ScanConfig, depth: int) -> Iterator[FileRecord]:
    """Walks the provided directory, creating FileRecords for each item until provided depth."""
    if depth >= config.max_depth:
        return

    try:
        # use a context manager for looping through directories since it handles garbage
        # collection
        with os.scandir(directory) as it:
            for entry in it:
                if entry.is_dir():
                    yield from _walk(entry.path, config, depth + 1)
                elif entry.is_file(follow_symlinks=False):
                    record = _make_record(entry, config)
                    if record:
                        yield record
    except PermissionError:
        logger.warning("Permission denied: %s", directory)


def _make_record(entry: DirEntry, config: ScanConfig) -> FileRecord | None:
    # we use entry of type `DirEntry` since its a lighterweight object and that it caches stat
    # info for free unlike a `Path` object, where as calling `.stat` on a Path obj requires an
    # extra call ?each time?
    try:
        # sanity check that we should actually make a record of this object, note we use lstrip
        # to handly files like .tar.gz, where we want `tar.gz`
        suffix = entry.name.split(".", 1)[1]
        if suffix in config.exclude_patterns:
            return

        size_mb = entry.stat().st_size / ONE_MB
        if size_mb < config.min_file_size_mb:
            return

        return FileRecord(
            path=Path(entry.path),
            ext=suffix,
            size_bytes=entry.stat().st_size,
            mtime=datetime.fromtimestamp(entry.stat().st_mtime, tz=timezone.utc),
            atime=datetime.fromtimestamp(entry.stat().st_atime, tz=timezone.utc),
        )
    except PermissionError:
        logger.warning("Permission denied: %s", entry)
