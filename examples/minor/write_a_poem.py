"""Example of a poem writing program using fabricatio."""

import asyncio
from typing import Any

from fabricatio import Action, Role, Task, WorkFlow, logger, Event
from fabricatio.models.usages import LLMUsage

task = Task(name="write poem")


class WritePoem(Action, LLMUsage):
    """Action that generates a poem."""

    output_key: str = "task_output"
    llm_stream: bool = False

    async def _execute(self, **_) -> Any:
        logger.info("Generating poem about the sea")
        return await self.ageneric_string(
            "Write a poetic and evocative poem about the sea, its vastness, and mysteries.",
        )


async def main() -> None:
    """Main function."""
    Role(
        name="poet",
        description="A role that creates poetic content",
        registry={Event.quick_instantiate(ns := 'poem'): WorkFlow(name="poetry_creation", steps=(WritePoem,))},
    )

    poem = await task.delegate(ns)
    logger.success(f"Poem:\n\n{poem}")


if __name__ == "__main__":
    asyncio.run(main())
