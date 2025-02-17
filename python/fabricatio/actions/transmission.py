"""Actions for transmitting tasks to targets."""

from typing import List

from fabricatio.journal import logger
from fabricatio.models.action import Action
from fabricatio.models.events import EventLike
from fabricatio.models.task import Task


class PublishTask(Action):
    """An action that publishes a task to a list of targets."""

    name: str = "publish_task"
    """The name of the action."""
    description: str = "Publish a task to a list of targets."
    """The description of the action."""

    async def _execute(self, send_targets: List[EventLike], send_task: Task, **_) -> None:
        """Execute the action by sending the task to the specified targets."""
        logger.info(f"Sending task {send_task.name} to {send_targets}")
        for target in send_targets:
            await send_task.move_to(target).publish()


class CycleTask(Action):
    """An action that cycles a task through a list of targets."""

    name: str = "cycle_task"
    """The name of the action."""
    description: str = "Cycle a task through a list of targets"

    async def _execute(self, task_input: Task, **_) -> None:
        """Execute the action by cycling the task through the specified targets."""
