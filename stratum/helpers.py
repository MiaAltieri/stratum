"""Helpers not belonging to a specific component"""

from pathlib import Path


def _read_version() -> str:
    version_path = Path(__file__).parent.parent / "version"
    with open(version_path, "r") as f:
        return f.read().strip()
