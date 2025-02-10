from typing import List

from fabricatio.journal import logger
from fabricatio.models.action import Action
from fabricatio.models.task import Task


class SendTask(Action):
    """Action that sends a task to a user."""

    name: str = "send_task"

    async def _execute(self, send_targets: List[str], send_task: Task, **_) -> None:
        logger.info(f"Sending task {send_task.name} to {send_targets}")
        for target in send_targets:
            await send_task.publish(target)
