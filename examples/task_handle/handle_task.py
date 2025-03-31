"""Example of using the library."""

import asyncio
from typing import Any, Set, Unpack

from fabricatio import Action, Event, PythonCapture, Role, Task, ToolBox, WorkFlow, logger, toolboxes
from pydantic import Field


class WriteCode(Action):
    """Action that says hello to the world."""

    output_key: str = "dump_text"

    async def _execute(self, task_input: Task[str], **_) -> str:
        return await self.aask_validate(
            task_input.briefing,
            system_message=task_input.dependencies_prompt,
            validator=PythonCapture.capture,
        )


class DumpText(Action):
    """Dump the text to a file."""

    toolboxes: Set[ToolBox] = Field(default_factory=lambda: {toolboxes.fs_toolbox})
    output_key: str = "task_output"

    async def _execute(self, task_input: Task, dump_text: str, **_: Unpack) -> Any:
        logger.debug(f"Dumping text: \n{dump_text}")
        task_input.update_task(
            ["dump the text contained in `text_to_dump` to a file", "only return the path of the written file"]
        )

        path = await self.handle(
            task_input,
            {"text_to_dump": dump_text},
        )
        if path:
            return path[0]

        return None


class WriteDocumentation(Action):
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
        registry={
            Event.quick_instantiate("coding"): WorkFlow(name="write code", steps=(WriteCode, DumpText)),
            Event.quick_instantiate("doc"): WorkFlow(name="write documentation", steps=(WriteDocumentation, DumpText)),
            Event.quick_instantiate("cancel_test"): WorkFlow(
                name="cancel_test",
                steps=(TestCancel, TestCancel, TestCancel, TestCancel, TestCancel, TestCancel, WriteToOutput),
                extra_init_context={"counter": 0},
            ),
        },
    )

    proposed_task = await role.propose_task(
        "i want you to write a cli app implemented with python , which can calculate the sum to a given n, all write to a single file names `cli.py`, put it in `output` folder."
    )
    path = await proposed_task.delegate("coding")
    logger.success(f"Code Path: {path}")

    proposed_task = await role.propose_task(
        f"write Readme.md file for the code, source file {path},save it in `README.md`,which is in the `output` folder, too."
    )
    proposed_task.override_dependencies(path)
    doc = await proposed_task.delegate("doc")
    logger.success(f"Documentation: \n{doc}")

    proposed_task.publish("cancel_test")
    await proposed_task.cancel()
    out = await proposed_task.get_output()
    logger.info(f"Canceled Task Output: {out}")


if __name__ == "__main__":
    asyncio.run(main())
