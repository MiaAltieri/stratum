"""Custom exceptions for Stratum."""

from pathlib import Path


class DirNotFoundException(Exception):
    def __init__(self, path: Path):
        super().__init__(f"Directory not found: {path}")
