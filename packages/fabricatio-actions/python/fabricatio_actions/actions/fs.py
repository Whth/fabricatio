"""A module for file system utilities."""

from pathlib import Path
from typing import Any, ClassVar, List, Mapping, Optional, Self

from fabricatio_core import Task
from fabricatio_core.capabilities.usages import UseLLM
from fabricatio_core.journal import logger
from fabricatio_core.models.action import Action
from fabricatio_core.utils import ok

from fabricatio_actions.models.generic import FromMapping

__all__ = ["DumpText", "ReadText", "SmartDumpText", "SmartReadText"]


class ReadText(Action, FromMapping):
    """Read text from a file."""

    ctx_override: ClassVar[bool] = True

    output_key: str = "read_text"
    read_path: Optional[str | Path] = None
    """Path to the file to read."""

    async def _execute(self, *_: Any, **cxt) -> str:
        p = Path(ok(self.read_path))
        logger.info(f"Read text from {p.as_posix()} to {self.output_key}")
        return p.read_text(encoding="utf-8")

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, str | Path], **kwargs: Any) -> List[Self]:
        """Create a list of ReadText actions from a mapping of output_key to read_path."""
        return [cls(read_path=p, output_key=k, **kwargs) for k, p in mapping.items()]


class DumpText(Action, FromMapping):
    """Dump text to a file."""

    ctx_override: ClassVar[bool] = True

    dump_path: Optional[str | Path] = None
    """Path to the file to dump."""
    text_key: str = "text"
    """Key of the text to dump."""

    async def _execute(self, *_: Any, **cxt) -> Any:
        p = Path(ok(self.dump_path))
        p.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Dump text from `{self.text_key}` to {p.as_posix()}")
        text = ok(cxt.get(self.text_key), f"Context key '{self.text_key}' not found")
        p.write_text(text, encoding="utf-8", errors="ignore")

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, str | Path], **kwargs: Any) -> List[Self]:
        """Create a list of DumpText actions from a mapping of output_key to dump_path."""
        return [cls(dump_path=p, text_key=k, **kwargs) for k, p in mapping.items()]


class SmartReadText(ReadText, UseLLM):
    """Read text from a file using LLM."""

    async def _execute(self, task_input: Task[str], *_: Any, **cxt) -> str:
        self.read_path = ok(
            self.read_path
            or await self.awhich_pathstr(
                f"{task_input.briefing}\n\nwhat is the file system path that the task needs to read?"
            )
        )

        return await super()._execute(*_, **cxt)


class SmartDumpText(DumpText, UseLLM):
    """Dump text to a file using LLM."""

    async def _execute(self, task_input: Task[str], *_: Any, **cxt) -> None:
        self.dump_path = ok(
            self.dump_path
            or await self.awhich_pathstr(
                f"{task_input.briefing}\n\nWhat is the file system path that the task needs write texts to?"
            )
        )

        await super()._execute(*_, **cxt)
