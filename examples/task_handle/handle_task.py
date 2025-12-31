"""Example of using the library."""

import asyncio
from typing import Any, Set

from fabricatio import Action, Event, Task, WorkFlow, logger
from fabricatio import Role as RoleBase
from fabricatio.capabilities import HandleTask, ProposeTask
from fabricatio.models import ToolBox, fs_toolbox
from fabricatio_core.capabilities.usages import UseLLM
from fabricatio_core.utils import ok
from pydantic import Field


class Role(RoleBase, ProposeTask):
    """Role that can propose tasks."""


class WriteCode(Action, UseLLM):
    """Action that says hello to the world."""

    output_key: str = "dump_text"

    async def _execute(self, task_input: Task[str], **_) -> str:
        return ok(await self.acode_string(f"{task_input.dependencies_prompt}\n\n{task_input.briefing}", "python"))


class DumpText(Action, HandleTask):
    """Dump the text to a file."""

    toolboxes: Set[ToolBox] = Field(default_factory=lambda: {fs_toolbox})
    output_key: str = "task_output"

    save_key: str = "save_path"

    async def _execute(self, task_input: Task, dump_text: str, **_) -> Any:
        logger.debug(f"Dumping text: \n{dump_text}")
        collector = ok(
            await self.handle(
                task_input.briefing, {"text_to_dump": dump_text}, {self.save_key: "the pathstr of the written file"}
            )
        )

        return collector.take(self.save_key, str)


class WriteDocumentation(Action, UseLLM):
    """Action that says hello to the world."""

    output_key: str = "dump_text"

    async def _execute(self, task_input: Task[str], **_) -> str:
        return await self.aask(task_input.briefing, system_message=task_input.dependencies_prompt)


class TestCancel(Action):
    """Action that says hello to the world."""

    output_key: str = "counter"

    async def _execute(self, counter: int, **_) -> int:
        logger.info(f"Counter: {counter}")
        await asyncio.sleep(5)
        counter += 1
        return counter


class WriteToOutput(Action):
    """Action that says hello to the world."""

    output_key: str = "task_output"

    async def _execute(self, **_) -> str:
        return "hi, this is the output"


async def main() -> None:
    """Main function."""
    role = Role(
        name="Coder",
        description="A python coder who can ",
        skills={
            Event.quick_instantiate("coding"): WorkFlow(name="write code", steps=(WriteCode, DumpText)),
            Event.quick_instantiate("doc"): WorkFlow(name="write documentation", steps=(WriteDocumentation, DumpText)),
            Event.quick_instantiate("cancel_test"): WorkFlow(
                name="cancel_test",
                steps=(TestCancel, TestCancel, TestCancel, TestCancel, TestCancel, TestCancel, WriteToOutput),
                extra_init_context={"counter": 0},
            ),
        },
    ).dispatch()

    proposed_task: Task[str] = ok(
        await role.propose_task(
            "i want you to write a cli app implemented with python , which can calculate the sum to a given n, all write to a single file names `cli.py`, put it in `output` folder."
        )
    )
    path = ok(await proposed_task.delegate("coding"))
    logger.info(f"Code Path: {path}")

    proposed_task = ok(
        await role.propose_task(
            f"write Readme.md file for the code, source file {path},save it in `README.md`,which is in the `output` folder, too."
        )
    )
    proposed_task.override_dependencies(path)
    doc = await proposed_task.delegate("doc")
    logger.info(f"Documentation: \n{doc}")

    proposed_task.publish("cancel_test")
    await proposed_task.cancel()
    out = await proposed_task.get_output()
    logger.info(f"Canceled Task Output: {out}")


if __name__ == "__main__":
    asyncio.run(main())
