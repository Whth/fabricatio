"""A module for file system utilities."""

from pathlib import Path
from typing import Any, List, Mapping, Self

from fabricatio_core.fs import safe_text_read
from fabricatio_core.journal import logger
from fabricatio_core.models.action import Action

from fabricatio_actions.models.generic import FromMapping


class ReadText(Action, FromMapping):
    """Read text from a file."""

    output_key: str = "read_text"
    read_path: str | Path
    """Path to the file to read."""

    async def _execute(self, *_: Any, **cxt) -> str:
        logger.info(f"Read text from {Path(self.read_path).as_posix()} to {self.output_key}")
        return safe_text_read(self.read_path)

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, str | Path], **kwargs: Any) -> List[Self]:
        """Create a list of ReadText actions from a mapping of output_key to read_path."""
        return [cls(read_path=p, output_key=k, **kwargs) for k, p in mapping.items()]
