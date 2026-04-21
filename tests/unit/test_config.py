"""Unit tests for stratum.config — config loader and validation."""

import textwrap
from pathlib import Path

import pytest
from pydantic import ValidationError

from stratum.config import ScanConfig, StratumConfig, SuggestionsConfig, load
from stratum.models import UploadConfig, UploadMode
from stratum.exceptions import DirNotFoundException

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write_toml(tmp_path: Path, content: str) -> Path:
    """Write a TOML string to a temp file and return its path."""
    p = tmp_path / "stratum.toml"
    p.write_text(textwrap.dedent(content))
    return p


# ---------------------------------------------------------------------------
# ScanConfig
# ---------------------------------------------------------------------------


class TestScanConfig:
    def test_valid_with_existing_dirs(self, tmp_path):
        d1 = tmp_path / "docs"
        d2 = tmp_path / "downloads"
        d1.mkdir()
        d2.mkdir()
        cfg = ScanConfig(watch_dirs=[d1, d2])
        assert cfg.watch_dirs == [d1, d2]

    def test_missing_dir_raises(self, tmp_path):
        missing = tmp_path / "does_not_exist"
        with pytest.raises(DirNotFoundException):
            ScanConfig(watch_dirs=[missing])

    def test_mixed_dirs_raises_on_missing(self, tmp_path):
        good = tmp_path / "good"
        good.mkdir()
        bad = tmp_path / "bad"
        with pytest.raises(DirNotFoundException):
            ScanConfig(watch_dirs=[good, bad])

    def test_watch_dirs_is_required(self):
        with pytest.raises(ValidationError):
            ScanConfig()

    def test_default_exclude_patterns(self, tmp_path):
        d = tmp_path / "d"
        d.mkdir()
        cfg = ScanConfig(watch_dirs=[d])
        assert cfg.exclude_patterns == ["DS_Store", "tmp", "git"]

    def test_custom_exclude_patterns(self, tmp_path):
        d = tmp_path / "d"
        d.mkdir()
        cfg = ScanConfig(watch_dirs=[d], exclude_patterns=["*.log"])
        assert cfg.exclude_patterns == ["log"]

    def test_default_min_file_size_mb(self, tmp_path):
        d = tmp_path / "d"
        d.mkdir()
        cfg = ScanConfig(watch_dirs=[d])
        assert cfg.min_file_size_mb == pytest.approx(0.1)

    def test_default_max_depth(self, tmp_path):
        d = tmp_path / "d"
        d.mkdir()
        cfg = ScanConfig(watch_dirs=[d])
        assert cfg.max_depth == 20

    def test_custom_values(self, tmp_path):
        d = tmp_path / "d"
        d.mkdir()
        cfg = ScanConfig(watch_dirs=[d], min_file_size_mb=1.5, max_depth=5)
        assert cfg.min_file_size_mb == pytest.approx(1.5)
        assert cfg.max_depth == 5


# ---------------------------------------------------------------------------
# SuggestionsConfig
# ---------------------------------------------------------------------------


class TestSuggestionsConfig:
    def test_defaults(self):
        cfg = SuggestionsConfig()
        assert cfg.log_path == Path("~/.stratum/suggestions.jsonl")
        assert cfg.dedup_enabled is True
        assert cfg.archive_days == 365
        assert cfg.reorganize is True

    def test_custom_values(self):
        cfg = SuggestionsConfig(
            log_path=Path("/tmp/s.jsonl"),
            dedup_enabled=False,
            archive_days=90,
            reorganize=False,
        )
        assert cfg.log_path == Path("/tmp/s.jsonl")
        assert cfg.dedup_enabled is False
        assert cfg.archive_days == 90
        assert cfg.reorganize is False


# ---------------------------------------------------------------------------
# StratumConfig
# ---------------------------------------------------------------------------


class TestStratumConfig:
    def test_suggestions_defaults_when_omitted(self, tmp_path):
        d = tmp_path / "d"
        d.mkdir()
        scan = ScanConfig(watch_dirs=[d])
        cfg = StratumConfig(scan=scan)
        assert cfg.suggestions == SuggestionsConfig()

    def test_scan_is_required(self):
        with pytest.raises(ValidationError):
            StratumConfig()

    def test_model_validate_empty_raises_on_missing_scan(self):
        with pytest.raises(ValidationError):
            StratumConfig.model_validate({})

    def test_model_validate_without_upload_section_succeeds(self, tmp_path):
        d = tmp_path / "d"
        d.mkdir()
        cfg = StratumConfig.model_validate({"scan": {"watch_dirs": [str(d)]}})
        assert isinstance(cfg, StratumConfig)

    def test_upload_defaults_when_section_absent(self, tmp_path):
        d = tmp_path / "d"
        d.mkdir()
        cfg = StratumConfig.model_validate({"scan": {"watch_dirs": [str(d)]}})
        assert cfg.upload.mode == UploadMode.METADATA_ONLY
        assert cfg.upload.prefix == "stratum/"


# ---------------------------------------------------------------------------
# load()
# ---------------------------------------------------------------------------


class TestLoad:
    def test_loads_valid_toml(self, tmp_path):
        d1 = tmp_path / "docs"
        d2 = tmp_path / "downloads"
        d1.mkdir()
        d2.mkdir()
        toml_path = write_toml(
            tmp_path,
            f"""
            [scan]
            watch_dirs = ["{d1}", "{d2}"]
            """,
        )
        cfg = load(toml_path)
        assert isinstance(cfg, StratumConfig)
        assert cfg.scan.watch_dirs == [d1, d2]

    def test_scan_defaults_applied(self, tmp_path):
        d = tmp_path / "d"
        d.mkdir()
        toml_path = write_toml(
            tmp_path,
            f"""
            [scan]
            watch_dirs = ["{d}"]
            """,
        )
        cfg = load(toml_path)
        assert cfg.scan.exclude_patterns == ["DS_Store", "tmp", "git"]
        assert cfg.scan.min_file_size_mb == pytest.approx(0.1)
        assert cfg.scan.max_depth == 20

    def test_suggestions_defaults_when_section_absent(self, tmp_path):
        d = tmp_path / "d"
        d.mkdir()
        toml_path = write_toml(
            tmp_path,
            f"""
            [scan]
            watch_dirs = ["{d}"]
            """,
        )
        cfg = load(toml_path)
        assert cfg.suggestions == SuggestionsConfig()

    def test_suggestions_overrides(self, tmp_path):
        d = tmp_path / "d"
        d.mkdir()
        toml_path = write_toml(
            tmp_path,
            f"""
            [scan]
            watch_dirs = ["{d}"]

            [suggestions]
            dedup_enabled = false
            archive_days = 90
            """,
        )
        cfg = load(toml_path)
        assert cfg.suggestions.dedup_enabled is False
        assert cfg.suggestions.archive_days == 90

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load(tmp_path / "nonexistent.toml")

    def test_missing_watch_dir_raises(self, tmp_path):
        toml_path = write_toml(
            tmp_path,
            """
            [scan]
            watch_dirs = ["/this/path/does/not/exist"]
            """,
        )
        with pytest.raises(DirNotFoundException):
            load(toml_path)

    def test_missing_scan_section_raises(self, tmp_path):
        toml_path = write_toml(tmp_path, "[suggestions]\narchive_days = 30\n")
        with pytest.raises(ValidationError):
            load(toml_path)

    def test_upload_section_loads_cleanly_when_present(self, tmp_path):
        d = tmp_path / "d"
        d.mkdir()
        toml_path = write_toml(
            tmp_path,
            f"""
            [scan]
            watch_dirs = ["{d}"]

            [upload]
            mode    = "METADATA_ONLY"
            bucket  = "my-stratum-archive"
            prefix  = "stratum/"
            region  = "us-east-1"
            profile = "stratum"
            """,
        )
        cfg = load(toml_path)
        assert cfg.upload.mode == UploadMode.METADATA_ONLY
        assert cfg.upload.bucket == "my-stratum-archive"
        assert cfg.upload.region == "us-east-1"

    def test_upload_section_absent_loads_cleanly(self, tmp_path):
        d = tmp_path / "d"
        d.mkdir()
        toml_path = write_toml(
            tmp_path,
            f"""
            [scan]
            watch_dirs = ["{d}"]
            """,
        )
        cfg = load(toml_path)
        assert isinstance(cfg.upload, UploadConfig)


# ---------------------------------------------------------------------------
# DirNotFoundException
# ---------------------------------------------------------------------------


class TestDirNotFoundException:
    def test_message_contains_path(self, tmp_path):
        missing = tmp_path / "missing"
        exc = DirNotFoundException(missing)
        assert str(missing) in str(exc)
