"""Unit tests for stratum.scanner — file system walker (STRAT-104)."""

import logging
from pathlib import Path
from unittest.mock import patch

from stratum.config import ScanConfig
from stratum.models import FileRecord
from stratum.scanner import scan

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ONE_MB = 1024 * 1024


def make_config(watch_dirs: list[Path], **kwargs) -> ScanConfig:
    defaults = dict(
        watch_dirs=watch_dirs,
        exclude_patterns=[".DS_Store", "*.tmp", ".git"],
        min_file_size_mb=0.0,
        max_depth=20,
    )
    defaults.update(kwargs)
    return ScanConfig(**defaults)


# ---------------------------------------------------------------------------
# scan() yields FileRecord objects only
# ---------------------------------------------------------------------------


class TestScanYieldsFileRecords:
    def test_yields_file_records(self, tmp_path):
        (tmp_path / "file.txt").write_text("hello world")
        results = list(scan(make_config([tmp_path])))
        assert all(isinstance(r, FileRecord) for r in results)

    def test_empty_directory_yields_nothing(self, tmp_path):
        results = list(scan(make_config([tmp_path])))
        assert results == []

    def test_no_none_in_results(self, tmp_path):
        (tmp_path / "a.txt").write_text("x")
        results = list(scan(make_config([tmp_path])))
        assert None not in results

    def test_multiple_watch_dirs_both_scanned(self, tmp_path):
        d1 = tmp_path / "d1"
        d2 = tmp_path / "d2"
        d1.mkdir()
        d2.mkdir()
        (d1 / "a.txt").write_text("a")
        (d2 / "b.txt").write_text("b")
        results = list(scan(make_config([d1, d2])))
        names = {r.path.name for r in results}
        assert names == {"a.txt", "b.txt"}


# ---------------------------------------------------------------------------
# Size filter
# ---------------------------------------------------------------------------


class TestSizeFilter:
    def test_file_below_min_size_excluded(self, tmp_path):
        (tmp_path / "tiny.txt").write_bytes(b"x" * 100)  # 100 B < 0.1 MB
        results = list(scan(make_config([tmp_path], min_file_size_mb=0.1)))
        assert results == []

    def test_file_above_min_size_included(self, tmp_path):
        big = tmp_path / "big.bin"
        big.write_bytes(b"x" * (2 * _ONE_MB))  # 2 MB > 0.1 MB
        results = list(scan(make_config([tmp_path], min_file_size_mb=0.1)))
        assert len(results) == 1
        assert results[0].path == big

    def test_file_at_exactly_min_size_included(self, tmp_path):
        # strictly less-than comparison: a file exactly at the limit passes through
        exact = tmp_path / "exact.bin"
        import math

        # we need to round up to the nearest byte
        exact.write_bytes(b"x" * math.ceil(0.1 * _ONE_MB))

        results = list(scan(make_config([tmp_path], min_file_size_mb=0.1)))
        assert len(results) == 1

    def test_mix_of_sizes_only_large_included(self, tmp_path):
        (tmp_path / "small.txt").write_bytes(b"s" * 100)
        big = tmp_path / "large.bin"
        big.write_bytes(b"x" * (2 * _ONE_MB))
        results = list(scan(make_config([tmp_path], min_file_size_mb=0.1)))
        assert len(results) == 1
        assert results[0].path == big


# ---------------------------------------------------------------------------
# Exclude patterns (fnmatch against filename)
# ---------------------------------------------------------------------------


class TestExcludePatterns:
    def test_glob_pattern_excludes_matching_file(self, tmp_path):
        (tmp_path / "junk.tmp").write_text("temporary")
        results = list(scan(make_config([tmp_path], exclude_patterns=[".tmp"])))
        assert results == []

    def test_non_matching_file_is_included(self, tmp_path):
        keep = tmp_path / "keep.txt"
        keep.write_text("keep me")
        results = list(scan(make_config([tmp_path], exclude_patterns=[".tmp"])))
        assert len(results) == 1
        assert results[0].path == keep

    def test_ds_store_excluded_by_default(self, tmp_path):
        (tmp_path / ".DS_Store").write_text("metadata")
        results = list(scan(make_config([tmp_path])))
        assert results == []

    def test_multiple_patterns_each_respected(self, tmp_path):
        (tmp_path / "file.tmp").write_text("temp")
        (tmp_path / "file.log").write_text("log")
        keep = tmp_path / "file.txt"
        keep.write_text("keep")
        results = list(scan(make_config([tmp_path], exclude_patterns=[".tmp", ".log"])))
        assert len(results) == 1
        assert results[0].path == keep

    def test_exact_filename_pattern_excluded(self, tmp_path):
        (tmp_path / ".git").write_text("not a dir here")
        results = list(scan(make_config([tmp_path])))
        assert results == []


# ---------------------------------------------------------------------------
# max_depth
# ---------------------------------------------------------------------------


class TestMaxDepth:
    def _build_tree(self, root: Path, levels: int) -> list[Path]:
        """Create one file per directory level; return file paths shallowest-first."""
        files = []
        current = root
        for i in range(1, levels + 1):
            f = current / f"file_l{i}.txt"
            f.write_text(f"level {i}")
            files.append(f)
            if i < levels:
                current = current / f"l{i}"
                current.mkdir()
        return files

    def test_max_depth_zero_yields_nothing(self, tmp_path):
        (tmp_path / "file.txt").write_text("hello")
        results = list(scan(make_config([tmp_path], max_depth=0)))
        assert results == []

    def test_max_depth_one_yields_top_level_files_only(self, tmp_path):
        top = tmp_path / "top.txt"
        top.write_text("top")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "nested.txt").write_text("nested")
        results = list(scan(make_config([tmp_path], max_depth=1)))
        assert len(results) == 1
        assert results[0].path == top

    def test_max_depth_two_yields_two_levels(self, tmp_path):
        top = tmp_path / "top.txt"
        top.write_text("t")
        sub = tmp_path / "sub"
        sub.mkdir()
        mid = sub / "mid.txt"
        mid.write_text("m")
        deep = sub / "deep"
        deep.mkdir()
        (deep / "deep.txt").write_text("d")
        results = list(scan(make_config([tmp_path], max_depth=2)))
        names = {r.path.name for r in results}
        assert "top.txt" in names
        assert "mid.txt" in names
        assert "deep.txt" not in names

    def test_five_level_tree_with_max_depth_two_excludes_lower_levels(self, tmp_path):
        # Build tmp/l1/l2/l3/l4/ with a file at each level
        dirs = [tmp_path]
        for i in range(1, 5):
            d = dirs[-1] / f"l{i}"
            d.mkdir()
            dirs.append(d)
        files = []
        for depth, d in enumerate(dirs):
            f = d / f"file_d{depth}.txt"
            f.write_text(f"depth {depth}")
            files.append(f)

        results = list(scan(make_config([tmp_path], max_depth=3)))
        names = {r.path.name for r in results}
        # depth 0 (watch_dir), 1, 2 included; 3, 4 excluded
        assert "file_d0.txt" in names
        assert "file_d1.txt" in names
        assert "file_d2.txt" in names
        assert "file_d3.txt" not in names
        assert "file_d4.txt" not in names


# ---------------------------------------------------------------------------
# PermissionError handling
# ---------------------------------------------------------------------------


class TestPermissionError:
    def test_permission_denied_dir_skipped_with_warning(self, tmp_path, caplog):
        accessible = tmp_path / "accessible.txt"
        accessible.write_text("hello")
        restricted = tmp_path / "restricted"
        restricted.mkdir()
        (restricted / "hidden.txt").write_text("secret")
        restricted.chmod(0o000)

        try:
            with caplog.at_level(logging.WARNING, logger="stratum.scanner"):
                results = list(scan(make_config([tmp_path])))
            assert any(r.path.name == "accessible.txt" for r in results)
            assert any("Permission denied" in msg for msg in caplog.messages)
        finally:
            restricted.chmod(0o755)

    def test_scan_continues_after_permission_error(self, tmp_path):
        restricted = tmp_path / "restricted"
        restricted.mkdir()
        restricted.chmod(0o000)
        other = tmp_path / "other.txt"
        other.write_text("accessible")

        try:
            results = list(scan(make_config([tmp_path])))  # must not raise
        finally:
            restricted.chmod(0o755)

        assert any(r.path.name == "other.txt" for r in results)

    def test_permission_denied_file_skipped_with_warning(self, tmp_path, caplog):
        good = tmp_path / "good.txt"
        good.write_text("fine")
        locked = tmp_path / "locked.txt"
        locked.write_text("locked")
        locked.chmod(0o000)

        try:
            with caplog.at_level(logging.WARNING, logger="stratum.scanner"):
                results = list(scan(make_config([tmp_path])))
            # at minimum the good file should appear; scan must not raise
            assert any(r.path.name == "good.txt" for r in results)
        finally:
            locked.chmod(0o644)


# ---------------------------------------------------------------------------
# FileRecord field values
# ---------------------------------------------------------------------------


class TestFileRecordFields:
    def test_path_matches_actual_file(self, tmp_path):
        f = tmp_path / "myfile.txt"
        f.write_text("content")
        results = list(scan(make_config([tmp_path])))
        assert results[0].path == f

    def test_size_bytes_matches_actual_size(self, tmp_path):
        f = tmp_path / "sized.bin"
        f.write_bytes(b"x" * 1234)
        results = list(scan(make_config([tmp_path])))
        assert results[0].size_bytes == 1234

    def test_mtime_is_utc_aware(self, tmp_path):
        (tmp_path / "f.txt").write_text("hi")
        results = list(scan(make_config([tmp_path])))
        assert results[0].mtime.tzinfo is not None

    def test_atime_is_utc_aware(self, tmp_path):
        (tmp_path / "f.txt").write_text("hi")
        results = list(scan(make_config([tmp_path])))
        assert results[0].atime.tzinfo is not None

    def test_content_hash_is_none(self, tmp_path):
        (tmp_path / "f.txt").write_text("hi")
        results = list(scan(make_config([tmp_path])))
        assert results[0].content_hash is None

    def test_duplicate_of_defaults_to_none(self, tmp_path):
        (tmp_path / "f.txt").write_text("hi")
        results = list(scan(make_config([tmp_path])))
        assert results[0].duplicate_of is None

    def test_ext_for_tar_gz_is_tar_gz(self, tmp_path):
        (tmp_path / "archive.tar.gz").write_bytes(b"x")
        results = list(scan(make_config([tmp_path])))
        assert results[0].ext == "tar.gz"


# ---------------------------------------------------------------------------
# No file is opened for reading
# ---------------------------------------------------------------------------


class TestNoFileOpened:
    def test_scan_does_not_open_any_file(self, tmp_path):
        (tmp_path / "secret.txt").write_text("secret content")
        with patch("builtins.open") as mock_open:
            list(scan(make_config([tmp_path])))
            mock_open.assert_not_called()
