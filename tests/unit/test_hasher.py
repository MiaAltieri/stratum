"""Unit tests for stratum.hasher — SHA-256 file content hasher (STRAT-105)."""

import hashlib
from pathlib import Path

import pytest

from stratum.hasher import CHUNK_SIZE, hash_file

# ---------------------------------------------------------------------------
# hash_file() returns a 64-character lowercase hex string
# ---------------------------------------------------------------------------


class TestHashFormat:
    def test_returns_64_character_string(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("hello world")
        result = hash_file(f)
        assert len(result) == 64

    def test_returns_lowercase_hex_string(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("hello world")
        result = hash_file(f)
        assert result == result.lower()
        assert all(c in "0123456789abcdef" for c in result)


# ---------------------------------------------------------------------------
# Two calls on the same file return identical results
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_same_file_same_hash(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("deterministic content")
        assert hash_file(f) == hash_file(f)


# ---------------------------------------------------------------------------
# Two files with identical content return the same hash
# ---------------------------------------------------------------------------


class TestIdenticalContent:
    def test_identical_content_same_hash(self, tmp_path):
        content = b"identical content bytes"
        f1 = tmp_path / "a.bin"
        f2 = tmp_path / "b.bin"
        f1.write_bytes(content)
        f2.write_bytes(content)
        assert hash_file(f1) == hash_file(f2)

    def test_empty_files_same_hash(self, tmp_path):
        f1 = tmp_path / "empty1.bin"
        f2 = tmp_path / "empty2.bin"
        f1.write_bytes(b"")
        f2.write_bytes(b"")
        assert hash_file(f1) == hash_file(f2)


# ---------------------------------------------------------------------------
# Two files with different content return different hashes
# ---------------------------------------------------------------------------


class TestDifferentContent:
    def test_different_content_different_hash(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("content A")
        f2.write_text("content B")
        assert hash_file(f1) != hash_file(f2)

    def test_one_byte_difference_different_hash(self, tmp_path):
        f1 = tmp_path / "a.bin"
        f2 = tmp_path / "b.bin"
        f1.write_bytes(b"hello")
        f2.write_bytes(b"hellp")
        assert hash_file(f1) != hash_file(f2)


# ---------------------------------------------------------------------------
# Calling hash_file on a non-existent path raises FileNotFoundError
# ---------------------------------------------------------------------------


class TestNonExistentPath:
    def test_missing_file_raises_file_not_found(self, tmp_path):
        missing = tmp_path / "does_not_exist.txt"
        with pytest.raises(FileNotFoundError):
            hash_file(missing)


# ---------------------------------------------------------------------------
# A file larger than CHUNK_SIZE is hashed correctly
# ---------------------------------------------------------------------------


class TestLargeFile:
    def test_file_larger_than_chunk_size_hashed_correctly(self, tmp_path):
        # 200 KB > CHUNK_SIZE (64 KB), so multiple reads are required
        large_content = b"x" * (200 * 1024)
        f = tmp_path / "large.bin"
        f.write_bytes(large_content)

        result = hash_file(f)

        expected = hashlib.sha256(large_content, usedforsecurity=False).hexdigest()
        assert result == expected

    def test_file_spanning_multiple_chunks_matches_expected(self, tmp_path):
        # Write content that spans exactly 3 chunks
        chunk_content = b"a" * CHUNK_SIZE
        content = chunk_content * 3
        f = tmp_path / "multi_chunk.bin"
        f.write_bytes(content)

        result = hash_file(f)

        expected = hashlib.sha256(content, usedforsecurity=False).hexdigest()
        assert result == expected
