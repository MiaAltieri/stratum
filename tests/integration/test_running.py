"""Integration tests: process execution, PID lifecycle, and suggestion log output."""

import os
from pathlib import Path

import pytest

import stratum.main as _main_module
from stratum.main import (
    PID_FILE_NAME,
    _delete_pid,
    _process_directory,
    _run_stratum,
    _write_pid,
)
from tests.integration.helpers import make_stratum_config, read_suggestions

_PID_PATH = Path(_main_module.__file__).parent / PID_FILE_NAME


@pytest.mark.integration
class TestEmptyDirectory:
    def test_empty_dir_scan_returns_zero_files_scanned(self, test_root, tmp_path):
        config = make_stratum_config(
            watch_dirs=[test_root / "empty_dir"],
            suggestions_dir=tmp_path,
        )
        result = _process_directory(config, dry_run=False)
        assert result.files_scanned == 0

    def test_empty_dir_scan_returns_zero_duplicates(self, test_root, tmp_path):
        config = make_stratum_config(
            watch_dirs=[test_root / "empty_dir"],
            suggestions_dir=tmp_path,
        )
        result = _process_directory(config, dry_run=False)
        assert result.duplicates_found == 0

    def test_empty_dir_scan_writes_no_suggestions(self, test_root, tmp_path):
        config = make_stratum_config(
            watch_dirs=[test_root / "empty_dir"],
            suggestions_dir=tmp_path,
        )
        _process_directory(config, dry_run=False)
        assert read_suggestions(tmp_path) == []


@pytest.mark.integration
class TestSuggestionLog:
    def test_suggestion_log_file_is_created_after_scan_with_duplicates(self, test_root, tmp_path):
        config = make_stratum_config(
            watch_dirs=[test_root / "main_scan_dir"],
            suggestions_dir=tmp_path,
        )
        _process_directory(config, dry_run=False)
        assert (tmp_path / "suggestions.jsonl").exists()

    def test_suggestion_log_contains_valid_jsonl_entries(self, test_root, tmp_path):
        config = make_stratum_config(
            watch_dirs=[test_root / "main_scan_dir"],
            suggestions_dir=tmp_path,
        )
        _process_directory(config, dry_run=False)
        entries = read_suggestions(tmp_path)
        assert len(entries) > 0
        for entry in entries:
            assert "action" in entry
            assert "path" in entry
            assert "reason" in entry
            assert "ts" in entry

    def test_suggestion_log_entries_match_suggestions_written_count(self, test_root, tmp_path):
        config = make_stratum_config(
            watch_dirs=[test_root / "main_scan_dir"],
            suggestions_dir=tmp_path,
        )
        result = _process_directory(config, dry_run=False)
        entries = read_suggestions(tmp_path)
        assert len(entries) == result.suggestions_written

    def test_suggestion_log_can_be_tailed(self, test_root, tmp_path):
        config = make_stratum_config(
            watch_dirs=[test_root / "main_scan_dir"],
            suggestions_dir=tmp_path,
        )
        _process_directory(config, dry_run=False)
        log_file = tmp_path / "suggestions.jsonl"
        lines = log_file.read_text(encoding="utf-8").splitlines()
        # Verify each line is individually parseable (tailable JSONL)
        import json

        for line in lines:
            if line.strip():
                parsed = json.loads(line)
                assert isinstance(parsed, dict)

    def test_no_suggestion_log_created_for_empty_dir(self, test_root, tmp_path):
        config = make_stratum_config(
            watch_dirs=[test_root / "empty_dir"],
            suggestions_dir=tmp_path,
        )
        _process_directory(config, dry_run=False)
        log_file = tmp_path / "suggestions.jsonl"
        # Log file may be created but should contain no entries
        assert read_suggestions(log_file) == []


@pytest.mark.integration
class TestPidFile:
    def test_write_pid_creates_file_at_expected_path(self):
        try:
            _write_pid()
            assert _PID_PATH.exists()
        finally:
            _delete_pid()

    def test_pid_file_contains_current_process_id(self):
        try:
            _write_pid()
            written_pid = int(_PID_PATH.read_text())
            assert written_pid == os.getpid()
        finally:
            _delete_pid()

    def test_delete_pid_removes_the_pid_file(self):
        _write_pid()
        assert _PID_PATH.exists()
        _delete_pid()
        assert not _PID_PATH.exists()

    def test_pid_file_is_absent_after_run_stratum_completes(self, test_root, tmp_path):
        config = make_stratum_config(
            watch_dirs=[test_root / "empty_dir"],
            suggestions_dir=tmp_path,
        )
        _run_stratum(config, dry_run=True)
        assert not _PID_PATH.exists()
