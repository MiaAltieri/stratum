"""Session-scoped test directory and cleanup fixtures for integration tests."""

import tempfile
from pathlib import Path

import pytest

import stratum.index as _index_module
import stratum.main as _main_module
from tests.integration.helpers import (
    CONTENT_A,
    CONTENT_B,
    CONTENT_C,
    CONTENT_D,
    CONTENT_E,
    CONTENT_F,
    CONTENT_G,
    CONTENT_SHARED_AB,
    CONTENT_SMALL,
    write_file,
)

_DB_PATH = Path(_index_module.__file__).parent / "index.db"
_PID_PATH = Path(_main_module.__file__).parent / "stratum.pid"


@pytest.fixture(autouse=True)
def cleanup_stratum_artifacts():
    """Remove the SQLite index and PID file before and after every integration test."""
    _DB_PATH.unlink(missing_ok=True)
    _PID_PATH.unlink(missing_ok=True)
    yield
    _DB_PATH.unlink(missing_ok=True)
    _PID_PATH.unlink(missing_ok=True)


@pytest.fixture(scope="session")
def test_root():
    """Create the shared test directory tree once for the entire integration session.

    Structure
    ---------
    main_scan_dir/      — mixed file types, excluded files, and duplicates at various depths
    dir_a/              — two unique-within-dir files; cross_dup shares content with dir_b
    dir_b/              — two unique-within-dir files; cross_dup shares content with dir_a
    dir_c/              — mirrors dir_a and dir_b as subdirs for combined-scan duplicate tests
    depth_test_dir/     — files at depths 0-3 for max_depth config tests
    empty_dir/          — no files, for empty-scan tests
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        # main_scan_dir: variety of file types + duplicates at two levels of depth
        main = root / "main_scan_dir"
        write_file(main / "doc_a.txt", CONTENT_A)
        write_file(main / "doc_b.txt", CONTENT_A)  # duplicate of doc_a.txt
        write_file(main / "photo.jpg", CONTENT_B)
        write_file(main / "script.py", CONTENT_C)
        write_file(main / "archive.zip", CONTENT_D)
        write_file(main / "document.pdf", CONTENT_E)
        write_file(main / "music.mp3", CONTENT_F)
        write_file(main / ".DS_Store", CONTENT_G)  # excluded by default pattern
        write_file(main / "ignored.tmp", CONTENT_G)  # excluded by default pattern
        write_file(main / "tiny.txt", CONTENT_SMALL)  # below min_file_size threshold
        write_file(main / "subdir" / "nested.txt", CONTENT_A)  # duplicate at depth 1
        write_file(main / "subdir" / "deep" / "deep_script.py", CONTENT_C)  # duplicate at depth 2

        # dir_a and dir_b: each internally unique, but share CONTENT_SHARED_AB across dirs
        write_file(root / "dir_a" / "cross_dup.txt", CONTENT_SHARED_AB)
        write_file(root / "dir_a" / "a_only.txt", CONTENT_A)
        write_file(root / "dir_b" / "cross_dup.txt", CONTENT_SHARED_AB)
        write_file(root / "dir_b" / "b_only.txt", CONTENT_B)

        # dir_c: contains copies of both dir_a and dir_b content for combined-scan tests
        write_file(root / "dir_c" / "subdir_a" / "cross_dup.txt", CONTENT_SHARED_AB)
        write_file(root / "dir_c" / "subdir_a" / "a_only.txt", CONTENT_A)
        write_file(root / "dir_c" / "subdir_b" / "cross_dup.txt", CONTENT_SHARED_AB)
        write_file(root / "dir_c" / "subdir_b" / "b_only.txt", CONTENT_B)

        # depth_test_dir: one file per directory level for max_depth tests
        depth_dir = root / "depth_test_dir"
        write_file(depth_dir / "level0.txt", b"L0" * 200)
        write_file(depth_dir / "sub1" / "level1.txt", b"L1" * 200)
        write_file(depth_dir / "sub1" / "sub2" / "level2.txt", b"L2" * 200)
        write_file(depth_dir / "sub1" / "sub2" / "sub3" / "level3.txt", b"L3" * 200)

        # empty_dir: no files
        (root / "empty_dir").mkdir()

        yield root
