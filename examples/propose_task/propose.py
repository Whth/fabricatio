"""Example of proposing a task to a role."""

import asyncio
from typing import Any

from fabricatio import Action, Event, Role, Task, WorkFlow, logger


class Talk(Action):
    """Action that says hello to the world."""

    output_key: str = "task_output"

    async def _execute(self, **_) -> Any:
        ret = "Hello fabricatio!"
        logger.info("executing talk action")
        return ret


async def main() -> None:
    """Main function."""
    role = Role(
        name="talker",
        description="talker role",
        registry={Event.quick_instantiate("talk"): WorkFlow(name="talk", steps=(Talk,))},
    )
    logger.info(f"Task example:\n{Task.formated_json_schema()}")
    logger.info(f"proposed task: {await role.propose_task('write a rust clap cli that can download a html page')}")


if __name__ == "__main__":
    asyncio.run(main())
