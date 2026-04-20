"""Shared utilities for Stratum integration tests."""

import json
from pathlib import Path

NORMAL_FILE_BYTES = 1024  # 1 KB, above the 0.0001 MB min_file_size threshold used in tests

# Unique byte patterns — each letter = distinct file content
CONTENT_A = b"A" * NORMAL_FILE_BYTES
CONTENT_B = b"B" * NORMAL_FILE_BYTES
CONTENT_C = b"C" * NORMAL_FILE_BYTES
CONTENT_D = b"D" * NORMAL_FILE_BYTES
CONTENT_E = b"E" * NORMAL_FILE_BYTES
CONTENT_F = b"F" * NORMAL_FILE_BYTES
CONTENT_G = b"G" * NORMAL_FILE_BYTES
CONTENT_SHARED_AB = b"S" * NORMAL_FILE_BYTES  # same content placed in both dir_a and dir_b
CONTENT_SMALL = b"x" * 50  # below the 0.0001 MB (~105 byte) threshold


def write_file(path: Path, content: bytes) -> None:
    """Write content to path, creating all parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def make_stratum_config(
    watch_dirs: list[Path],
    suggestions_dir: Path,
    *,
    min_file_size_mb: float = 0.0001,
    max_depth: int = 20,
    exclude_patterns: list[str] | None = None,
):
    """Build a StratumConfig for the given directories without writing a TOML file."""
    from stratum.config import ScanConfig, SuggestionsConfig, StratumConfig

    if exclude_patterns is None:
        exclude_patterns = ["DS_Store", "tmp", "git"]

    scan = ScanConfig(
        watch_dirs=watch_dirs,
        min_file_size_mb=min_file_size_mb,
        max_depth=max_depth,
        exclude_patterns=exclude_patterns,
    )
    suggestions = SuggestionsConfig(log_path=suggestions_dir)
    return StratumConfig(scan=scan, suggestions=suggestions)


def read_suggestions(suggestions_dir: Path) -> list[dict]:
    """Return all suggestion entries from the JSONL log inside suggestions_dir."""
    log_file = suggestions_dir / "suggestions.jsonl"
    if not log_file.exists():
        return []
    entries = []
    for line in log_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries
