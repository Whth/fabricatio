"""Persistence capabilities for model instances."""

from abc import ABC
from datetime import datetime
from pathlib import Path
from typing import Optional, Self

from loguru import logger

from fabricatio.fs import safe_text_read
from fabricatio.models.generic import Base
from fabricatio.rust import blake3_hash


class PersistentAble(Base, ABC):
    """Class providing file persistence capabilities.

    Enables saving model instances to disk with timestamped filenames and loading from persisted files.
    Implements basic versioning through filename hashing and timestamping.
    """

    def persist(self, path: str | Path) -> Self:
        """Save model instance to disk with versioned filename.

        Args:
            path (str | Path): Target directory or file path. If directory, filename is auto-generated.

        Returns:
            Self: Current instance for method chaining

        Notes:
            - Filename format: <ClassName>_<YYYYMMDD_HHMMSS>_<6-char_hash>.json
            - Hash generated from JSON content ensures uniqueness
        """
        p = Path(path)
        out = self.model_dump_json(indent=1, by_alias=True)

        # Generate a timestamp in the format YYYYMMDD_HHMMSS
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Generate the hash
        file_hash = blake3_hash(out.encode())[:6]

        # Construct the file name with timestamp and hash
        file_name = f"{self.__class__.__name__}_{timestamp}_{file_hash}.json"

        if p.is_dir():
            p.joinpath(file_name).write_text(out, encoding="utf-8")
        else:
            p.mkdir(exist_ok=True, parents=True)
            p.write_text(out, encoding="utf-8")

        logger.info(f"Persisted `{self.__class__.__name__}` to {p.as_posix()}")
        return self

    @classmethod
    def from_latest_persistent(cls, dir_path: str | Path) -> Optional[Self]:
        """Load most recent persisted instance from directory.

        Args:
            dir_path (str | Path): Directory containing persisted files

        Returns:
            Self: Most recently modified instance

        Raises:
            NotADirectoryError: If path is not a valid directory
            FileNotFoundError: If no matching files found
        """
        dir_path = Path(dir_path)
        if not dir_path.is_dir():
            return None

        pattern = f"{cls.__name__}_*.json"
        files = list(dir_path.glob(pattern))

        if not files:
            return None

        def _get_timestamp(file_path: Path) -> datetime:
            stem = file_path.stem
            parts = stem.split("_")
            return datetime.strptime(f"{parts[1]}_{parts[2]}", "%Y%m%d_%H%M%S")

        files.sort(key=lambda f: _get_timestamp(f), reverse=True)

        return cls.from_persistent(files.pop(0))

    @classmethod
    def from_persistent(cls, path: str | Path) -> Self:
        """Load an instance from a specific persisted file.

        Args:
            path (str | Path): Path to the JSON file.

        Returns:
            Self: The loaded instance from the file.

        Raises:
            FileNotFoundError: If the specified file does not exist.
            ValueError: If the file content is invalid for the model.
        """
        return cls.model_validate_json(safe_text_read(path))
