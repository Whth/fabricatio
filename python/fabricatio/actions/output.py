"""Dump the finalized output to a file."""

from fabricatio.models.action import Action
from fabricatio.models.generic import FinalizedDumpAble
from fabricatio.models.task import Task
from fabricatio.models.utils import ok


class DumpFinalizedOutput(Action):
    """Dump the finalized output to a file."""

    output_key: str = "dump_path"

    async def _execute(self, task_input: Task, to_dump: FinalizedDumpAble, **_) -> str:
        dump_path = ok(
            await self.awhich_pathstr(
                f"{task_input.briefing}\n\nExtract a single path of the file, to which I will dump the data."
            ),
            "Could not find the path of file to dump the data.",
        )

        to_dump.finalized_dump_to(dump_path)
        return dump_path
