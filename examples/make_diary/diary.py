"""Example of using the library."""

import asyncio
from datetime import datetime
from typing import Optional, Set, Unpack

from fabricatio import Action, Event, Role, Task, WorkFlow, logger, toolboxes
from fabricatio.fs.readers import safe_json_read
from fabricatio.models.tool import ToolBox
from pydantic import Field


class WriteDiary(Action):
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
        json_data = task_input.pop_dependence(reader=safe_json_read)
        seq = sorted(json_data.items(), key=lambda x: datetime.strptime(x[0], "%Y-%m-%d"))

        res = await self.aask(
            task_input.briefing,
            system_message=[
                f"{c}\nWrite a diary for the {d},according to the commits, 不要太流水账或者只是将commit翻译为中文,应该着重与高级的设计抉择和设计思考,保持日记整体200字左右。"
                for d, c in seq
            ],
            temperature=1.5,
            top_p=1.0,
        )

        return "\n\n\n".join(res)


class DumpText(Action):
    """Dump the text to a file."""

    toolboxes: Set[ToolBox] = Field(default_factory=lambda: {toolboxes.fs_toolbox})
    output_key: str = "task_output"

    async def _execute(self, task_input: Task, dump_text: str, **_: Unpack) -> Optional[str]:
        logger.debug(f"Dumping text: \n{dump_text}")
        task_input.update_task(
            ["dump the text contained in `text_to_dump` to a file", "only return the path of the written file"]
        )

        path = await self.handle_fine_grind(
            task_input,
            {"text_to_dump": dump_text},
        )
        if path:
            return path[0]

        return None


async def main() -> None:
    """Main function."""
    role = Role(
        name="Coder",
        description="A python coder who can ",
        registry={
            Event.quick_instantiate("doc"): WorkFlow(name="write documentation", steps=(WriteDiary, DumpText)),
        },
    )

    task = await role.propose_task(
        "Write a diary according to the given commit messages in json format. and dump to `diary.md` at `output` dir,"
        "In the json the key is the day in which the commit messages in value was committed,"
        "you need to separately write diary for each day.",
    )
    task.override_dependencies("./commits.json")
    await task.move_to("doc").delegate()


if __name__ == "__main__":
    asyncio.run(main())
