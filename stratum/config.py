"""Configuration loader for Stratum — reads and validates stratum.toml."""

import tomllib
import logging

from pathlib import Path
from typing import List

from pydantic import BaseModel, field_validator

from stratum.exceptions import DirNotFoundException

logger = logging.getLogger(__name__)


class ScanConfig(BaseModel):
    """ScanConfig describes the settings that control how the file scanner behaves."""

    watch_dirs: List[Path]
    exclude_patterns: List[str] = ["DS_Store", "tmp", "git"]
    min_file_size_mb: float = 0.1
    max_depth: int = 20

    @field_validator("watch_dirs", mode="after")
    @classmethod
    def normalise_dirs(cls, values: List[Path]) -> List[Path]:
        normalised = []
        for val in values:
            normalised.append(val.expanduser())

        return normalised

    @field_validator("watch_dirs", mode="after")
    @classmethod
    def validate_dirs_existence(cls, value: List[Path]) -> List[Path]:
        for dir_name in value:
            if not dir_name.is_dir():
                logger.error("Did not find directory: %s", dir_name)
                raise DirNotFoundException(dir_name)
        return value

    @field_validator("exclude_patterns", mode="before")
    @classmethod
    def normalise_extensions(cls, values: List[str]) -> List[str]:
        normalised = []
        for val in values:
            # Strip leading "*.", ".", or "*" then take the extension part
            # we must `lstrip` because we could have .tar.gz and we will want the full ext
            ext = val.lstrip("*").lstrip(".")
            normalised.append(ext)

        return normalised


class SuggestionsConfig(BaseModel):
    """Default settings for suggestion logger."""

    log_path: Path = Path("~/.stratum/suggestions.jsonl")
    dedup_enabled: bool = True
    archive_days: int = 365
    reorganize: bool = True


class StratumConfig(BaseModel):
    """Top level config obeject."""

    scan: ScanConfig
    suggestions: SuggestionsConfig = SuggestionsConfig()


def load(path: Path = Path("~/.stratum/stratum.toml")) -> StratumConfig:
    resolved = path.expanduser()
    with resolved.open("rb") as f:
        data = tomllib.load(f)
    return StratumConfig.model_validate(data)
