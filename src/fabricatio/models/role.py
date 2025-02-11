from typing import Any

from pydantic import Field

from fabricatio.core import env
from fabricatio.journal import logger
from fabricatio.models.action import WorkFlow
from fabricatio.models.events import Event
from fabricatio.models.generic import ProposeTask


class Role(ProposeTask):
    """Class that represents a role with a registry of events and workflows."""

    registry: dict[Event | str, WorkFlow] = Field(...)
    """ The registry of events and workflows."""

    def model_post_init(self, __context: Any) -> None:
        """Register the workflows in the role to the event bus."""
        for event, workflow in self.registry.items():
            workflow.fallback_to(self).fallback_to_self()
            workflow.inject_personality(self.briefing)
            logger.debug(
                f"Registering workflow: {workflow.name} for event: {event.collapse() if isinstance(event, Event) else event}"
            )
            env.on(event, workflow.serve)
