"""Dump the finalized output to a file."""

from pathlib import Path
from typing import Optional

from fabricatio.journal import logger
from fabricatio.models.action import Action
from fabricatio.models.generic import FinalizedDumpAble, PersistentAble
from fabricatio.models.task import Task
from fabricatio.models.utils import ok


class DumpFinalizedOutput(Action):
    """Dump the finalized output to a file."""

    output_key: str = "dump_path"

    async def _execute(
        self,
        to_dump: FinalizedDumpAble,
        task_input: Optional[Task] = None,
        dump_path: Optional[str | Path] = None,
        **_,
    ) -> str:
        dump_path = Path(
            dump_path
            or ok(
                await self.awhich_pathstr(
                    f"{ok(task_input, 'Neither `task_input` and `dump_path` is provided.').briefing}\n\nExtract a single path of the file, to which I will dump the data."
                ),
                "Could not find the path of file to dump the data.",
            )
        )
        ok(to_dump, "Could not dump the data since the path is not specified.").finalized_dump_to(dump_path)
        return dump_path.as_posix()


class PersistentAll(Action):
    """Persist all the data to a file."""

    output_key: str = "persistent_count"

    async def _execute(
        self,
        task_input: Optional[Task] = None,
        persist_dir: Optional[str | Path] = None,
        **cxt,
    ) -> int:
        persist_dir = Path(
            persist_dir
            or ok(
                await self.awhich_pathstr(
                    f"{ok(task_input, 'Neither `task_input` and `dump_path` is provided.').briefing}\n\nExtract a single path of the file, to which I will persist the data."
                ),
                "Can not find the path of file to persist the data.",
            )
        )

        count = 0
        if persist_dir.is_file():
            logger.warning("Dump should be a directory, but it is a file. Skip dumping.")
            return count
        persist_dir.mkdir(parents=True, exist_ok=True)
        for v in cxt.values():
            if isinstance(v, PersistentAble):
                v.persist(persist_dir)
                count += 1

        return count
