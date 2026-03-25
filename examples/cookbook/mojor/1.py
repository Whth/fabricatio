"""Example of a simple hello world program using fabricatio."""

from typing import Any

from fabricatio import Action, Event, Role, Task, WorkFlow, logger


class Hello(Action):  # The class name is the name of the action
    """Action that says hello."""

    output_key: str = "task_output"

    # Key name, but currently it does not support being custom captured by
    # the workflow, so it is recommended to use: "task_output"

    async def _execute(self, **_) -> Any:
        # The return value of this function will be stored in the context dictionary
        ret_2 = "say or say"
        logger.info("No")
        # Print log
        return ret_2


class Say(Action):
    """an Action."""

    output_key: str = "task1"

    async def _execute(self, *_: Any, **cxt) -> Any:
        return "hello or hello"


# When creating a workflow, explicitly specify the
# name, steps, and task_output_key parameters
work = WorkFlow(
    name="Thing 1",  # name
    steps=(
        Hello,
        Say,
    ),  # Actions to be performed, multiple actions possible
    task_output_key="take1",
    # Customization is currently not supported.
    # Even if set to "take1", it will only query "task_output",
    # and if there are multiple "task_output" entries,
    # it will take the result of the last operation.
)

(
    Role(name="ai", description="description")  # Character Names and Descriptions
    .add_skill(Event.quick_instantiate("123"), work)
    # Event("123") (the author calls it a skill, hehe)
    # can trigger the character and execute the workflow
    .dispatch()
    # Activate this character;
    # if not activated, even encountering this event will not execute
)

result = Task(name="1").delegate_blocking("123")
# Create a Task, and have it acted upon by the character of the eventskill ("123")
logger.info(f"Result: {result}")
if result is not None:
    logger.info(result)
