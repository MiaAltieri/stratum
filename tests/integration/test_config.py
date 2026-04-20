"""Integration tests: config settings take effect end-to-end."""

import pytest

from stratum.main import _process_directory

from tests.integration.helpers import make_stratum_config, read_suggestions


@pytest.mark.integration
class TestDirectoryDepthConfig:
    def test_files_within_max_depth_are_scanned(self, test_root, tmp_path):
        config = make_stratum_config(
            watch_dirs=[test_root / "depth_test_dir"],
            suggestions_dir=tmp_path,
            max_depth=20,
        )
        result = _process_directory(config, dry_run=True)
        assert result.files_scanned == 4  # level0, level1, level2, level3

    def test_max_depth_one_excludes_all_subdirectory_files(self, test_root, tmp_path):
        # depth=0 is the watch dir itself; the scanner returns early when depth >= max_depth
        config = make_stratum_config(
            watch_dirs=[test_root / "depth_test_dir"],
            suggestions_dir=tmp_path,
            max_depth=1,
        )
        result = _process_directory(config, dry_run=True)
        assert result.files_scanned == 1  # only level0.txt

    def test_max_depth_two_stops_before_second_subdir(self, test_root, tmp_path):
        config = make_stratum_config(
            watch_dirs=[test_root / "depth_test_dir"],
            suggestions_dir=tmp_path,
            max_depth=2,
        )
        result = _process_directory(config, dry_run=True)
        assert result.files_scanned == 2  # level0.txt and level1.txt


@pytest.mark.integration
class TestExcludePatternsConfig:
    def test_ds_store_files_are_excluded_by_default(self, test_root, tmp_path):
        config = make_stratum_config(
            watch_dirs=[test_root / "main_scan_dir"],
            suggestions_dir=tmp_path,
        )
        _process_directory(config, dry_run=False)
        suggested_paths = [s["path"] for s in read_suggestions(tmp_path)]
        assert not any(".DS_Store" in p for p in suggested_paths)

    def test_tmp_files_are_excluded_by_default(self, test_root, tmp_path):
        config = make_stratum_config(
            watch_dirs=[test_root / "main_scan_dir"],
            suggestions_dir=tmp_path,
        )
        _process_directory(config, dry_run=False)
        suggested_paths = [s["path"] for s in read_suggestions(tmp_path)]
        assert not any(".tmp" in p for p in suggested_paths)

    def test_custom_exclude_pattern_skips_matching_extension(self, test_root, tmp_path):
        config = make_stratum_config(
            watch_dirs=[test_root / "main_scan_dir"],
            suggestions_dir=tmp_path,
            exclude_patterns=["py"],
        )
        _process_directory(config, dry_run=False)
        suggested_paths = [s["path"] for s in read_suggestions(tmp_path)]
        assert not any(p.endswith(".py") for p in suggested_paths)


@pytest.mark.integration
class TestMinFileSizeConfig:
    def test_files_below_size_threshold_are_not_scanned(self, test_root, tmp_path):
        # tiny.txt is 50 bytes; threshold 0.0001 MB ≈ 105 bytes → tiny.txt excluded
        config = make_stratum_config(
            watch_dirs=[test_root / "main_scan_dir"],
            suggestions_dir=tmp_path,
            min_file_size_mb=0.0001,
        )
        result = _process_directory(config, dry_run=False)
        all_paths = [s["path"] for s in read_suggestions(tmp_path)]
        assert not any("tiny.txt" in p for p in all_paths)
        # Files above the threshold are counted
        assert result.files_scanned > 0

    def test_raising_size_threshold_reduces_scanned_count(self, test_root, tmp_path):
        config_low = make_stratum_config(
            watch_dirs=[test_root / "main_scan_dir"],
            suggestions_dir=tmp_path,
            min_file_size_mb=0.0001,
        )
        result_low = _process_directory(config_low, dry_run=True)

        config_high = make_stratum_config(
            watch_dirs=[test_root / "main_scan_dir"],
            suggestions_dir=tmp_path / "high",
            min_file_size_mb=10.0,  # 10 MB — no test files are this large
        )
        result_high = _process_directory(config_high, dry_run=True)

        assert result_high.files_scanned < result_low.files_scanned


@pytest.mark.integration
class TestMultipleWatchDirsConfig:
    def test_single_watch_dir_scans_its_files(self, test_root, tmp_path):
        config = make_stratum_config(
            watch_dirs=[test_root / "dir_a"],
            suggestions_dir=tmp_path,
        )
        result = _process_directory(config, dry_run=True)
        assert result.files_scanned == 2  # cross_dup.txt and a_only.txt

    def test_multiple_watch_dirs_combine_scanned_counts(self, test_root, tmp_path):
        config = make_stratum_config(
            watch_dirs=[test_root / "dir_a", test_root / "dir_b"],
            suggestions_dir=tmp_path,
        )
        result = _process_directory(config, dry_run=True)
        assert result.files_scanned == 4  # 2 from dir_a + 2 from dir_b
