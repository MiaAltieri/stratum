"""Main orchestrator and CLI entry point for Stratum."""

import argparse
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from stratum.config import load
from stratum.hasher import hash_file
from stratum.index import StratumIndex
from stratum.models import ScanMetadata, SuggestionAction, SuggestionEntry
from stratum.scanner import scan
from stratum.suggestion_log import SuggestionLogger
from stratum.tagger import classify

PID_FILE_NAME = "stratum.pid"

SCANNED = "files_scanned"
DUPS_FOUND = "duplicates_found"
SUGGS_WRIT = "suggestions_written"
DUR_S = "duration_seconds"

logger = logging.getLogger(__name__)


def run() -> None:
    """CLI entry point wired via pyproject.toml [project.scripts].

    Future PR: handle DirNotFoundException gracefully.
    """
    logging.basicConfig(
        level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s"
    )
    logger.info("BEGINNING STRATUM")
    args = _parse_args()
    config = load(args.config_path)

    logger.info("Running straum with config: %s", config)
    logger.info("Running straum in dry_run: %s", args.dry_run)
    _run_stratum(config, args.dry_run)


def _run_stratum(config, dry_run=bool) -> None:
    """Handle straum process.

    As of now this doesn't need to be a separate function, but when we introduct multithreading
    we will want to be able to handle multiple threads and I think this will be useful for
    managment. Note this is subject to change.
    """
    try:
        _write_pid()
        scan_metadata = _process_directory(config, dry_run)
        # NOTE in the future think about how we to print work summary, by thread or combined?
        print("Job complete, summary: ", scan_metadata)
    finally:  # TODO consider which types of exceptions we will want to handle
        _delete_pid()

        # we delete the DB so that future tests in different dirs won't incorrectly have different
        # indexes
        with StratumIndex() as db:
            db.del_db(path=Path(__file__).parent / "index.db")


def _write_pid() -> None:
    # NOTE in the future we will want to think on how we can handle PID when we introduce
    # multithreading
    pid_path = Path(__file__).parent / PID_FILE_NAME
    pid_path.parent.mkdir(parents=True, exist_ok=True)

    with open(pid_path, "w") as f:
        f.write(str(os.getpid()))


def _delete_pid():
    pid_path = Path(__file__).parent / PID_FILE_NAME
    if os.path.exists(pid_path):
        os.remove(pid_path)


def _process_directory(config, dry_run) -> ScanMetadata:
    """The scan loop:
    * during loop: log scan progress with the stdlib logging module (not print statements).
    -> emit suggestion if duplicate

    """
    scan_data = {
        SCANNED: 0,
        DUPS_FOUND: 0,
        SUGGS_WRIT: 0,
        DUR_S: 0,
    }

    start = time.monotonic()

    with (
        StratumIndex() as db,
        SuggestionLogger(config.suggestions.log_path) as sug_logger,
    ):
        # run scan
        for record in scan(config.scan):
            scan_data[SCANNED] += 1

            # run hasher
            file_hash = hash_file(record.path)

            # check duplicate
            duplicate_path = db.contains(file_hash)
            is_dup = duplicate_path is not None

            # run tagger
            tag = classify(record.ext)

            # complete the record
            record = record.model_copy(
                update={
                    "file_type": tag,
                    "content_hash": file_hash,
                    "is_duplicate": is_dup,
                }
            )

            if duplicate_path is not None and str(duplicate_path) != str(record.path):
                scan_data[DUPS_FOUND] += 1
                scan_data[SUGGS_WRIT] += 1

                duplicate_entry = SuggestionEntry(
                    ts=datetime.now(timezone.utc),
                    action=SuggestionAction.DELETE_DUPLICATE,
                    path=record.path,
                    reason=f"Identical content to {duplicate_path}",
                    size_bytes=record.size_bytes,
                )

                if dry_run:
                    print(record.path, "is identical to", duplicate_path)
                else:
                    sug_logger.suggest(duplicate_entry)

            db.insert(file_hash, record.path)

    elapsed = time.monotonic() - start
    scan_data[DUR_S] = int(elapsed)
    return ScanMetadata.model_validate(scan_data)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stratum file scanner")
    p.add_argument("--config_path", type=Path, default=Path("~/.stratum/stratum.toml"))
    p.add_argument("--dry_run", type=bool, default=True)
    return p.parse_args()
