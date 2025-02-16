"""Module that contains the Role class."""

from typing import Any, Set

from fabricatio.core import env
from fabricatio.journal import logger
from fabricatio.models.action import WorkFlow
from fabricatio.models.events import Event
from fabricatio.models.task import ProposeTask
from fabricatio.models.tool import ToolBox, ToolBoxUsage
from fabricatio.toolboxes import basic_toolboxes
from pydantic import Field


class Role(ProposeTask, ToolBoxUsage):
    """Class that represents a role with a registry of events and workflows."""

    registry: dict[Event | str, WorkFlow] = Field(...)
    """ The registry of events and workflows."""

    toolboxes: Set[ToolBox] = Field(default=basic_toolboxes)

    def model_post_init(self, __context: Any) -> None:
        """Register the workflows in the role to the event bus."""
        for event, workflow in self.registry.items():
            (
                workflow.fallback_to(self)
                .steps_fallback_to_self()
                .inject_personality(self.briefing)
                .supply_tools_from(self)
                .steps_supply_tools_from_self()
            )

            logger.debug(
                f"Registering workflow: {workflow.name} for event: {event.collapse() if isinstance(event, Event) else event}"
            )
            env.on(event, workflow.serve)
