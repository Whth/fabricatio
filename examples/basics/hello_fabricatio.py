"""Example of a simple hello world program using fabricatio."""

from typing import Any

from fabricatio import Action, Event, Role, Task, WorkFlow, logger
from fabricatio_core.utils import ok


class Hello(Action):
    """Action that says hello."""

    output_key: str = "task_output"

    async def _execute(self, **_) -> Any:
        ret = "Hello fabricatio!"
        logger.info("executing talk action")
        return ret


(
    Role(name="talker", description="talker role")
    .add_skill(Event.quick_instantiate("talk"), WorkFlow(name="talk", steps=(Hello,)))
    .dispatch()
)

logger.info(ok(Task(name="say hi").delegate_blocking("talk")))
