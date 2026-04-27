"""Demonstrates using Fabricatio to generate structured content from raw data — reading commit messages in JSON format and producing an internship diary in markdown. Shows how task goals and dependencies guide LLM output."""

import asyncio
from datetime import datetime
from typing import Any, Dict, Optional, Set

from fabricatio import Action, Event, Task, WorkFlow, logger
from fabricatio import Role as RoleBase
from fabricatio.capabilities import Handle
from fabricatio.models import ToolBox
from fabricatio_capabilities.capabilities.task import ProposeTask
from fabricatio_core.capabilities.usages import UseLLM
from fabricatio_core.models.role import EventPattern
from fabricatio_core.utils import ok
from fabricatio_tool import toolboxes
from fabricatio_tool.fs import safe_json_read
from pydantic import Field


class WriteDiary(Action, UseLLM):
    """Write a diary according to the given commit messages in json format."""

    output_key: str = "dump_text"

    async def _execute(self, task_input: Task[str], **_) -> str:
        task_input.goals.clear()
        task_input.goals.extend(
            [
                "write a Internship Diary according to the given commit messages",
                "the diary should include the main dev target of the day, and the exact content"
                ", and make a summary of the day, what have been learned, and what had felt",
                "diary should be written in markdown format, and using Chinese to write",
                "write dev target and exact content under the heading names `# 实习主要项目和内容`",
                "write summary under the heading names `# 主要收获和总结`",
            ]
        )

        # 2025-02-22 format
        json_data = task_input.read_dependency(reader=safe_json_read)
        seq = sorted(json_data.items(), key=lambda x: datetime.strptime(x[0], "%Y-%m-%d"))

        res = await self.aask(
            [
                f"{task_input.briefing}\n{c}\nWrite a diary for the {d},according to the commits, 不要太流水账或者只是将commit翻译为中文,应该着重与高级的设计抉择和设计思考,保持日记整体200字左右。"
                for d, c in seq
            ],
            temperature=1.5,
            top_p=1.0,
        )

        return "\n\n\n".join(res)


class DumpText(Action, Handle):
    """Dump the text to a file."""

    toolboxes: Set[ToolBox] = Field(default_factory=lambda: {toolboxes.fs_toolbox})
    output_key: str = "task_output"

    async def _execute(self, task_input: Task, dump_text: str, **_: Any) -> Optional[str]:
        logger.debug(f"Dumping text: \n{dump_text}")
        task_input.update_task(
            goal=["dump the text contained in `text_to_dump` to a file", "only return the path of the written file"]
        )

        resc = await self.handle_fine_grind(
            task_input.assembled_prompt, {"text_to_dump": dump_text}, {"written_file_path": "path of the written file"}
        )
        if resc:
            return resc.take("written_file_path")

        return None


class Coder(RoleBase, ProposeTask):
    """A role that can write a diary according to the given commit messages in json format."""

    skills: Dict[EventPattern, WorkFlow] = Field(
        default={
            Event.quick_instantiate("doc").collapse(): WorkFlow(
                name="write documentation", steps=(WriteDiary, DumpText)
            ),
        }
    )


async def main() -> None:
    """Run the diary generation pipeline: propose a task to write diary entries from commit JSON, inject the commit data as a dependency, then delegate to the diary-writing workflow."""
    role = Coder()

    task = ok(
        await role.propose_task(
            "Write a diary according to the given commit messages in json format. and dump to `diary.md` at `output` dir,"
            "In the json the key is the day in which the commit messages in value was committed,"
            "you need to separately write diary for each day.",
        )
    )
    task.override_dependencies("./commits.json")
    await task.move_to("doc").delegate()


if __name__ == "__main__":
    asyncio.run(main())
