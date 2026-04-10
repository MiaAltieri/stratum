"""Content hasher — computes SHA-256 hex digests of file contents."""

import hashlib
from pathlib import Path

CHUNK_SIZE = 65_536  # 64 KB


def hash_file(path: Path) -> str:
    """Return the SHA-256 hex digest of the file at *path*."""
    h = hashlib.sha256(usedforsecurity=False)
    # use context manager for happy file handling and we read as bytes since weare generating a
    # hash.
    # NOTE: open doesn't actually load the entire file, it just establishes the connection
    with path.open("rb") as f:
        # read one chunk at a time
        while chunk := f.read(CHUNK_SIZE):
            h.update(chunk)

    # human readible hash
    return h.hexdigest()
