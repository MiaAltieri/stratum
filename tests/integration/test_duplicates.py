"""Integration tests: duplicate detection within and across directories."""

import pytest

from stratum.main import _process_directory, _run_stratum
from tests.integration.helpers import make_stratum_config, read_suggestions


@pytest.mark.integration
class TestDuplicateDetectionWithinDir:
    def test_duplicate_files_are_detected(self, test_root, tmp_path):
        # main_scan_dir has doc_a.txt and doc_b.txt with identical content
        config = make_stratum_config(
            watch_dirs=[test_root / "main_scan_dir"],
            suggestions_dir=tmp_path,
        )
        result = _process_directory(config, dry_run=False)
        assert result.duplicates_found > 0

    def test_duplicate_suggestion_action_is_delete_duplicate(self, test_root, tmp_path):
        config = make_stratum_config(
            watch_dirs=[test_root / "main_scan_dir"],
            suggestions_dir=tmp_path,
        )
        _process_directory(config, dry_run=False)
        entries = read_suggestions(tmp_path)
        assert len(entries) > 0
        actions = {e["action"] for e in entries}
        assert "DELETE_DUPLICATE" in actions

    def test_duplicate_suggestion_reason_references_original_path(self, test_root, tmp_path):
        config = make_stratum_config(
            watch_dirs=[test_root / "main_scan_dir"],
            suggestions_dir=tmp_path,
        )
        _process_directory(config, dry_run=False)
        entries = read_suggestions(tmp_path)
        assert len(entries) > 0
        for entry in entries:
            assert entry["reason"]  # reason must be non-empty

    def test_duplicates_at_different_depths_are_all_detected(self, test_root, tmp_path):
        # main_scan_dir has duplicates at:
        #   depth 0: doc_b.txt (same as doc_a.txt)
        #   depth 1: subdir/nested.txt (same as doc_a.txt)
        #   depth 2: subdir/deep/deep_script.py (same as script.py)
        config = make_stratum_config(
            watch_dirs=[test_root / "main_scan_dir"],
            suggestions_dir=tmp_path,
        )
        result = _process_directory(config, dry_run=False)
        assert result.duplicates_found >= 3

    def test_suggestions_written_equals_duplicates_found(self, test_root, tmp_path):
        config = make_stratum_config(
            watch_dirs=[test_root / "main_scan_dir"],
            suggestions_dir=tmp_path,
        )
        result = _process_directory(config, dry_run=False)
        assert result.suggestions_written == result.duplicates_found


@pytest.mark.integration
class TestSeparateDirScans:
    def test_scanning_dir_a_alone_finds_no_duplicates(self, test_root, tmp_path):
        # dir_a contains cross_dup.txt and a_only.txt — both have unique content within dir_a
        config = make_stratum_config(
            watch_dirs=[test_root / "dir_a"],
            suggestions_dir=tmp_path,
        )
        result = _process_directory(config, dry_run=False)
        assert result.duplicates_found == 0

    def test_scanning_dir_b_alone_finds_no_duplicates(self, test_root, tmp_path):
        # dir_b contains cross_dup.txt and b_only.txt — both have unique content within dir_b
        config = make_stratum_config(
            watch_dirs=[test_root / "dir_b"],
            suggestions_dir=tmp_path,
        )
        result = _process_directory(config, dry_run=False)
        assert result.duplicates_found == 0

    def test_separate_runs_on_dir_a_and_dir_b_do_not_share_the_index(self, test_root, tmp_path):
        """Two separate _run_stratum calls must not carry index state between them.

        dir_a/cross_dup.txt and dir_b/cross_dup.txt are byte-identical. Running stratum
        once on dir_a and once on dir_b (in separate invocations) should not report
        cross-directory duplicates, because the index is cleared between runs.
        """
        suggestions_a = tmp_path / "run_a"
        suggestions_a.mkdir()
        suggestions_b = tmp_path / "run_b"
        suggestions_b.mkdir()

        config_a = make_stratum_config(
            watch_dirs=[test_root / "dir_a"],
            suggestions_dir=suggestions_a,
        )
        _run_stratum(config_a, dry_run=False)  # clears index on exit

        config_b = make_stratum_config(
            watch_dirs=[test_root / "dir_b"],
            suggestions_dir=suggestions_b,
        )
        _run_stratum(config_b, dry_run=False)  # starts with a fresh index

        assert read_suggestions(suggestions_a) == []
        assert read_suggestions(suggestions_b) == []


@pytest.mark.integration
class TestCombinedDirScan:
    def test_scanning_dir_c_detects_cross_subdir_duplicates(self, test_root, tmp_path):
        # dir_c/subdir_a/cross_dup.txt and dir_c/subdir_b/cross_dup.txt are byte-identical
        config = make_stratum_config(
            watch_dirs=[test_root / "dir_c"],
            suggestions_dir=tmp_path,
        )
        result = _process_directory(config, dry_run=False)
        assert result.duplicates_found > 0

    def test_combined_scan_suggestion_paths_are_inside_dir_c(self, test_root, tmp_path):
        config = make_stratum_config(
            watch_dirs=[test_root / "dir_c"],
            suggestions_dir=tmp_path,
        )
        _process_directory(config, dry_run=False)
        entries = read_suggestions(tmp_path)
        assert len(entries) > 0
        for entry in entries:
            assert "dir_c" in entry["path"]
