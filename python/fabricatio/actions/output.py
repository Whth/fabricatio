"""Dump the finalized output to a file."""

from pathlib import Path
from typing import Optional

from fabricatio.models.action import Action
from fabricatio.models.generic import FinalizedDumpAble
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
