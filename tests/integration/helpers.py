"""Shared utilities for Stratum integration tests."""

import json
import tomli_w
from pathlib import Path

NORMAL_FILE_BYTES = (
    1024  # 1 KB, above the 0.0001 MB min_file_size threshold used in tests
)

# Unique byte patterns — each letter = distinct file content
CONTENT_A = b"A" * NORMAL_FILE_BYTES
CONTENT_B = b"B" * NORMAL_FILE_BYTES
CONTENT_C = b"C" * NORMAL_FILE_BYTES
CONTENT_D = b"D" * NORMAL_FILE_BYTES
CONTENT_E = b"E" * NORMAL_FILE_BYTES
CONTENT_F = b"F" * NORMAL_FILE_BYTES
CONTENT_G = b"G" * NORMAL_FILE_BYTES
CONTENT_SHARED_AB = (
    b"S" * NORMAL_FILE_BYTES
)  # same content placed in both dir_a and dir_b
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
    config_dir: Path | None = None,
    return_path: bool = False,
):
    """Write a stratum.toml to config_dir (or suggestions_dir) and load config from it."""
    from stratum import config as config_module

    if exclude_patterns is None:
        exclude_patterns = ["DS_Store", "tmp", "git"]

    toml_dir = config_dir if config_dir is not None else suggestions_dir
    toml_dir.mkdir(parents=True, exist_ok=True)
    toml_path = toml_dir / "stratum.toml"

    data = {
        "scan": {
            "watch_dirs": [str(p) for p in watch_dirs],
            "min_file_size_mb": min_file_size_mb,
            "max_depth": max_depth,
            "exclude_patterns": exclude_patterns,
        },
        "suggestions": {
            "log_path": str(suggestions_dir),
        },
    }
    toml_path.write_bytes(tomli_w.dumps(data).encode())

    if return_path:
        return toml_path

    return config_module.load(toml_path)


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
