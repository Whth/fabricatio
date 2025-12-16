"""A module for file system utilities."""

from pathlib import Path
from typing import Any, List, Mapping, Self

from fabricatio_core import Task
from fabricatio_core.capabilities.usages import UseLLM
from fabricatio_core.journal import logger
from fabricatio_core.models.action import Action
from fabricatio_core.utils import ok

from fabricatio_actions.models.generic import FromMapping


class ReadText(Action, FromMapping):
    """Read text from a file."""

    output_key: str = "read_text"
    read_path: str | Path
    """Path to the file to read."""

    async def _execute(self, *_: Any, **cxt) -> str:
        logger.info(f"Read text from {Path(self.read_path).as_posix()} to {self.output_key}")
        return Path(self.read_path).read_text(encoding="utf-8")

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, str | Path], **kwargs: Any) -> List[Self]:
        """Create a list of ReadText actions from a mapping of output_key to read_path."""
        return [cls(read_path=p, output_key=k, **kwargs) for k, p in mapping.items()]


class DumpText(Action, FromMapping):
    """Dump text to a file."""

    dump_path: str | Path
    """Path to the file to dump."""
    text_key: str = "text"
    """Key of the text to dump."""

    async def _execute(self, *_: Any, **cxt) -> Any:
        p = Path(self.dump_path)
        logger.info(f"Dump text from `{self.text_key}` to {p.as_posix()}")
        p.write_text(cxt[self.text_key], encoding="utf-8", errors="ignore")

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, str | Path], **kwargs: Any) -> List[Self]:
        """Create a list of DumpText actions from a mapping of output_key to dump_path."""
        return [cls(dump_path=p, text_key=k, **kwargs) for k, p in mapping.items()]


class SmartReadText(ReadText, UseLLM):
    """Read text from a file using LLM."""

    async def _execute(self, task_input: Task[str], *_: Any, **cxt) -> str:
        self.read_path = ok(
            self.read_path or await self.awhich_pathstr(f"{task_input.briefing}\n\nWhere is the file you need to read?")
        )

        return await super()._execute(*_, **cxt)


class SmartDumpText(DumpText, UseLLM):
    """Dump text to a file using LLM."""

    async def _execute(self, task_input: Task[str], *_: Any, **cxt) -> str:
        self.dump_path = ok(
            self.dump_path
            or await self.awhich_pathstr(f"{task_input.briefing}\n\nWhere is the file you need to dump the text to?")
        )

        return await super()._execute(*_, **cxt)
