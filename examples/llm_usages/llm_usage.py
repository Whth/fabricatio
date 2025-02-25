"""Example of using the library."""

import asyncio

from fabricatio import Action, Role, Task, WorkFlow
from fabricatio.journal import logger
from fabricatio.models.events import Event
from fabricatio.parser import PythonCapture


class WriteCode(Action):
    """Action that says hello to the world."""

    name: str = "write code"
    output_key: str = "task_output"

    async def _execute(self, task_input: Task[str], **_) -> str:
        return await self.aask_validate(
            task_input.briefing,
            validator=PythonCapture.capture,
        )


class WriteDocumentation(Action):
    """Action that says hello to the world."""

    name: str = "write documentation"
    description: str = "write documentation for the code in markdown format"
    output_key: str = "task_output"

    async def _execute(self, task_input: Task[str], **_) -> str:
        return await self.aask(task_input.briefing, task_input.dependencies_prompt)


async def main() -> None:
    """Main function."""
    role = Role(
        name="Coder",
        description="A python coder who can write code and documentation",
        registry={
            Event.instantiate_from("coding").push_wildcard().push("pending"): WorkFlow(
                name="write code", steps=(WriteCode,)
            ),
            Event.instantiate_from("doc").push_wildcard().push("pending"): WorkFlow(
                name="write documentation", steps=(WriteDocumentation,)
            ),
        },
    )

    prompt = "write a python cli app which can add a list of numbers writen in a file together,with detailed google style documentation."

    proposed_task = await role.propose(prompt)
    code = await proposed_task.move_to("coding").delegate()
    logger.success(f"Code: \n{code}")

    proposed_task = await role.propose(f"{code} \n\n write Readme.md file for the code.")
    doc = await proposed_task.move_to("doc").delegate()
    logger.success(f"Documentation: \n{doc}")


if __name__ == "__main__":
    asyncio.run(main())
