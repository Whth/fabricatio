from typing import Any

from pydantic import Field, ValidationError

from fabricatio.core import env
from fabricatio.journal import logger
from fabricatio.models.action import WorkFlow
from fabricatio.models.events import Event
from fabricatio.models.generic import LLMUsage, Memorable, WithBriefing, WithToDo
from fabricatio.models.task import Task
from fabricatio.parser import JsonCapture


class Role(Memorable, WithBriefing, WithToDo, LLMUsage):
    """Class that represents a role with a registry of events and workflows."""

    registry: dict[Event | str, WorkFlow] = Field(...)
    """ The registry of events and workflows."""

    def model_post_init(self, __context: Any) -> None:
        """Register the workflows in the role to the event bus."""
        for event, workflow in self.registry.items():
            workflow.fallback_to(self)
            logger.debug(
                f"Registering workflow: {workflow.name} for event: {event.collapse() if isinstance(event, Event) else event}"
            )
            env.on(event, workflow.serve)

    async def propose(self, prompt: str) -> Task:
        """Propose a task based on the provided prompt."""
        assert prompt, "Prompt must be provided."

        def _validate_json(response: str) -> None | Task:
            try:
                cap = JsonCapture.capture(response)
                logger.debug(f"Response: \n{response}")
                logger.info(f"Captured JSON: \n{cap[0]}")
                return Task.model_validate_json(cap[0] if cap else response)
            except ValidationError as e:
                logger.error(f"Failed to parse task from JSON: {e}")
                return None

        return await self.aask_validate(
            f"{prompt} \n\nBased on requirement above, "
            f"you need to construct a task to satisfy that requirement in JSON format "
            f"written like this: \n\n```json\n{Task.json_example()}\n```\n\n"
            f"No extra explanation needed. ",
            _validate_json,
            system_message=f"# your personal briefing: \n{self.briefing}",
        )
