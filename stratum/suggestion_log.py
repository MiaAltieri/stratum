"""Suggestion logger — appends advisory SuggestionEntry records to a JSONL file."""

import logging
from pathlib import Path

from stratum.models import SuggestionEntry

logger = logging.getLogger(__name__)
SUGGESTION_FILE_NAME = "suggestions.jsonl"


class CalledOutsideContextManager(RuntimeError):
    """Raised when SuggestionLogger methods are called outside a `with` block."""


class SuggestionLogger:
    def __init__(self, log_path: Path):
        self.log_path = log_path.expanduser()
        self._file_conn = None

    def __enter__(self) -> "SuggestionLogger":
        try:
            self.log_path.mkdir(parents=True, exist_ok=True)
            self._file_conn = (self.log_path / SUGGESTION_FILE_NAME).open("a", encoding="utf-8")
            return self
        except Exception as e:
            logger.error("Exception with logger connection:", e)
            self.__exit__()
            raise

    def __exit__(self, *_) -> None:
        if self._file_conn:
            self._file_conn.close()
            self._file_conn = None

    def suggest(self, entry: SuggestionEntry) -> None:
        """Append *entry* as a single JSON line."""
        if not self._file_conn:
            raise CalledOutsideContextManager(
                "SuggestionLogger.suggest() must be called inside a `with` block."
            )
        self._file_conn.write(entry.model_dump_json() + "\n")
        self._file_conn.flush()
