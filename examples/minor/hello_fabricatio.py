"""Example of a simple hello world program using fabricatio."""

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

    """Main function."""


(Role().register_workflow(Event.quick_instantiate("talk"), WorkFlow(name="talk", steps=(Hello,))).dispatch())

logger.success(task.delegate_blocking("talk"))
