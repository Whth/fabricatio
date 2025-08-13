"""Example of a simple hello world program using fabricatio."""

from typing import Any

from fabricatio import Action, Event, Role, Task, WorkFlow, logger


class Hello(Action):
    """Action that says hello."""

    output_key: str = "task_output"

    async def _execute(self, **_) -> Any:
        ret = "Hello fabricatio!"
        logger.info("executing talk action")
        return ret

    """Main function."""


(
    Role(name="talker", description="talker role")
    .register_workflow(Event.quick_instantiate("talk"), WorkFlow(name="talk", steps=(Hello,)))
    .dispatch()
)

logger.info(Task(name="say hi").delegate_blocking("talk"))
