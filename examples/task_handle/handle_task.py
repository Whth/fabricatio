"""Example of using the library."""

import asyncio
from typing import Any, Set, Unpack

from fabricatio import Action, Event, PythonCapture, Role, Task, ToolBox, WorkFlow, fs_toolbox, logger
from pydantic import Field


class WriteCode(Action):
    """Action that says hello to the world."""

    name: str = "write code"
    output_key: str = "source_code"

    async def _execute(self, task_input: Task[str], **_) -> str:
        return await self.aask_validate(
            task_input.briefing,
            system_message=task_input.dependencies_prompt,
            validator=PythonCapture.capture,
        )


class DumpCode(Action):
    """Dump code to file system."""

    name: str = "dump code"
    description: str = "dump code to file system"
    toolboxes: Set[ToolBox] = Field(default_factory=lambda: {fs_toolbox})
    output_key: str = "task_output"

    async def _execute(self, task_input: Task, source_code: str, **_: Unpack) -> Any:
        task_input.goal.append("return the path where the source_code is written.")
        path = await self.handle_fin_grind(
            task_input,
            {"source_code": source_code},
        )
        if path:
            return path[0]

        return None


class WriteDocumentation(Action):
    """Action that says hello to the world."""

    name: str = "write documentation"
    description: str = "write documentation for the code in markdown format"
    output_key: str = "task_output"

    async def _execute(self, task_input: Task[str], **_) -> str:
        return await self.aask(task_input.briefing)


async def main() -> None:
    """Main function."""
    role = Role(
        name="Coder",
        description="A python coder who can ",
        registry={
            Event.instantiate_from("coding.*").push("pending"): WorkFlow(
                name="write code", steps=(WriteCode, DumpCode)
            ),
            Event.instantiate_from("doc.*").push("pending"): WorkFlow(
                name="write documentation", steps=(WriteDocumentation,)
            ),
        },
    )

    prompt = "write a python cli app which can print a 'hello world' with give times, with detailed google style docstring. write the source code to `cli.py`"

    proposed_task = await role.propose(prompt)
    path = await proposed_task.move_to("coding").delegate()
    logger.info(f"Code Path: {path}")
    #
    # proposed_task = await role.propose(f"{code} \n\n write Readme.md file for the code.")
    # proposed_task.add_dependency()
    # doc = await proposed_task.move_to("doc").delegate()
    # logger.success(f"Documentation: \n{doc}")


if __name__ == "__main__":
    asyncio.run(main())
