"""Example of a simple hello world program using fabricatio."""

import asyncio
from typing import Any

from fabricatio import Action, Event, Role, Task, WorkFlow, logger

task = Task(name="say hello")


class Hello(Action):
    """Action that says hello."""

    output_key: str = "task_output"

    async def _execute(self, **_) -> Any:
        ret = "Hello fabricatio!"
        logger.info("executing talk action")
        return ret


async def main() -> None:
    """Main function."""
    Role(name="talker", description="talker role",
         registry={Event.quick_instantiate("talk"): WorkFlow(name="talk", steps=(Hello,))})

    logger.success(f"Result: {await task.delegate("talk")}")


if __name__ == "__main__":
    asyncio.run(main())
