from typing import Any

from pydantic import Field

from fabricatio.core import env
from fabricatio.journal import logger
from fabricatio.models.action import WorkFlow
from fabricatio.models.events import Event
from fabricatio.models.generic import LLMUsage, Memorable, WithBriefing, WithToDo
from fabricatio.models.task import Task


class Role(Memorable, WithBriefing, WithToDo, LLMUsage):
    """Class that represents a role with a registry of events and workflows."""

    registry: dict[Event | str, WorkFlow] = Field(...)
    """ The registry of events and workflows."""

    def model_post_init(self, __context: Any) -> None:
        for event, workflow in self.registry.items():
            workflow.fallback_to(self)
            logger.debug(
                f"Registering workflow: {workflow.name} for event: {event.collapse() if isinstance(event, Event) else event}"
            )
            env.on(event, workflow.serve)

    async def propose(self, prompt: str) -> Task:
        """Propose a task to the role."""
