"""Helpers not belonging to a specific component"""


def _read_version() -> str:
    with open("version", "r") as f:
        return f.read().strip()
