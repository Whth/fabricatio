"""Example of proposing a task to a role."""

import asyncio
from typing import Any

from fabricatio import Action, Role, Task, WorkFlow, logger

task = Task(name="say hello", goal="say hello", description="say hello to the world")


class Talk(Action):
    """Action that says hello to the world."""

    name: str = "talk"
    output_key: str = "task_output"

    async def _execute(self, **_) -> Any:
        ret = "Hello fabricatio!"
        logger.info("executing talk action")
        return ret


async def main() -> None:
    """Main function."""
    role = Role(
        name="talker", description="talker role", registry={task.pending_label: WorkFlow(name="talk", steps=(Talk,))}
    )
    logger.info(f"Task example:\n{Task.json_example()}")
    logger.info(f"proposed task: {await role.propose('write a rust clap cli that can download a html page')}")


if __name__ == "__main__":
    asyncio.run(main())
