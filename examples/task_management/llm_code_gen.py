"""Demonstrate how to use Fabricatio's LLM capabilities (UseLLM, Propose) to build a code-generation agent that writes code AND documentation from a single prompt."""

import asyncio

from fabricatio import Action, Event, Task, WorkFlow, logger
from fabricatio import Role as RoleBase
from fabricatio.capabilities import Propose
from fabricatio_capabilities.capabilities.task import ProposeTask
from fabricatio_core.capabilities.usages import UseLLM
from fabricatio_core.rust import python_parser


class Role(RoleBase, ProposeTask):
    """A coding agent role that can propose tasks and compose code solutions."""


class WriteCode(Action, Propose):
    """Generate Python code from a natural-language briefing. Uses LLM with Python syntax validation to ensure the output is valid Python."""

    output_key: str = "task_output"

    async def _execute(self, task_input: Task[str], **_) -> str:
        return await self.aask_validate(
            task_input.briefing,
            validator=python_parser.cap,
        )


class WriteDocumentation(UseLLM, Action):
    """Generate markdown documentation for previously generated code. Takes the code as a dependency via task chaining."""

    output_key: str = "task_output"

    async def _execute(self, task_input: Task[str], **_) -> str:
        return await self.aask(task_input.briefing, task_input.dependencies_prompt)


async def main() -> None:
    """Demonstrate a two-step code generation pipeline: first generate Python code, then generate README documentation for that code using task dependency chaining."""
    role = Role(
        name="Coder",
        description="A python coder who can write code and documentation",
        skills={
            Event.quick_instantiate("coding").collapse(): WorkFlow(name="write code", steps=(WriteCode,)),
            Event.quick_instantiate("doc").collapse(): WorkFlow(
                name="write documentation", steps=(WriteDocumentation,)
            ),
        },
    )

    prompt = "write a python cli app which can add a list of numbers writen in a file together,with detailed google style documentation."

    proposed_task = await role.propose_task(prompt)
    code = await proposed_task.move_to("coding").delegate()
    logger.info(f"Code: \n{code}")

    proposed_task = await role.propose_task(f"{code} \n\n write Readme.md file for the code.")
    doc = await proposed_task.move_to("doc").delegate()
    logger.info(f"Documentation: \n{doc}")


if __name__ == "__main__":
    asyncio.run(main())
