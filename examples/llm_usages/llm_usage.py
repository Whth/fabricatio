"""Example of using the library."""

import asyncio
from typing import Any, Callable

from fabricatio import Action, Role, Task, WorkFlow, logger
from fabricatio.parser import PythonCapture

task = Task(name="say hello", goal="say hello", description="say hello to the world")


class Talk(Action):
    """Action that says hello to the world."""

    name: str = "talk"
    output_key: str = "task_output"

    async def _execute(self, task_input: Task[str], **_) -> Any:
        def _validator(res: str) -> Callable[[float, float], float] | None:
            code = PythonCapture.capture(res)
            exec(code, None, locals())
            if "addup" in locals():
                return locals().get("addup")
            return None

        func = await self.aask_validate(
            "make a python function which can compute addition of two numbers, with good typing, the function name shall be `addup`"
        )
        logger.info("executing talk action")
        return func


async def main() -> None:
    """Main function."""
    role = Role(
        name="talker", description="talker role", registry={task.pending_label: WorkFlow(name="talk", steps=(Talk,))}
    )


if __name__ == "__main__":
    asyncio.run(main())
