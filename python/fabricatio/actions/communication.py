"""Actions that involve communication with the user."""

from fabricatio.models.action import Action
from fabricatio.models.task import Task


class Talk(Action):
    """Action that says hello to the world."""

    name: str = "talk"
    output_key: str = "talk_response"

    async def _execute(self, task_input: Task[str], **_) -> str:
        """Execute the action."""
        return await self.aask(task_input.briefing, system_message=task_input.dependencies_prompt())
