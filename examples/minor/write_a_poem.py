"""Example of a poem writing program using fabricatio."""

import asyncio
from typing import Any, Optional

from fabricatio import Action, Event, Role, Task, WorkFlow, logger
from fabricatio.models.usages import LLMUsage


class WritePoem(Action, LLMUsage):
    """Action that generates a poem."""

    output_key: str = "task_output"
    llm_stream: Optional[bool] = False

    async def _execute(self, task_input: Task[str], **_) -> Any:
        logger.info(f"Generating poem about \n{task_input.briefing}")
        return await self.ageneric_string(
            f"{task_input.briefing}\nWrite a poetic",
        )


async def main() -> None:
    """Main function."""
    Role(
        name="poet",
        description="A role that creates poetic content",
        registry={Event.quick_instantiate(ns := "poem"): WorkFlow(name="poetry_creation", steps=(WritePoem,))},
    )
    task = Task(
        name="write poem",
        description="Write a poem about the given topic, in this case, write a poem about the fire",
        goals=["THe poem should be about fire", "The poem should be short"],
    )
    poem = await task.delegate(ns)
    logger.success(f"Poem:\n\n{poem}")


if __name__ == "__main__":
    asyncio.run(main())
