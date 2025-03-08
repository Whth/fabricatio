"""Dump the finalized output to a file."""

from typing import Unpack

from fabricatio.models.action import Action
from fabricatio.models.generic import FinalizedDumpAble
from fabricatio.models.task import Task


class DumpFinalizedOutput(Action):
    """Dump the finalized output to a file."""

    output_key: str = "dump_path"

    async def _execute(self, task_input: Task, to_dump: FinalizedDumpAble, **cxt: Unpack) -> str:
        dump_path = await self.awhich_pathstr(
            f"{task_input.briefing}\n\nExtract a single path of the file, to which I will dump the data."
        )

        to_dump.finalized_dump_to(dump_path)
        return dump_path
