"""Example of a poem writing program using fabricatio."""

import asyncio
from typing import Any

from fabricatio import Action, Role, Task, WorkFlow, logger

task = Task(name="write poem")


class WritePoem(Action):
    """Action that generates a poem."""

    output_key: str = "task_output"

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
        registry={task.pending_label: WorkFlow(name="poetry_creation", steps=(WritePoem,))},
    )

    poem = await task.delegate()
    logger.success(f"Poem:\n\n{poem}")


if __name__ == "__main__":
    asyncio.run(main())
