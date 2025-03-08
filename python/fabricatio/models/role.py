"""Module that contains the Role class."""

from typing import Any, Self, Set

from fabricatio.capabilities.review import Review
from fabricatio.capabilities.task import HandleTask, ProposeTask
from fabricatio.core import env
from fabricatio.journal import logger
from fabricatio.models.action import WorkFlow
from fabricatio.models.events import Event
from fabricatio.models.tool import ToolBox
from pydantic import Field


class Role(ProposeTask, HandleTask, Review):
    """Class that represents a role with a registry of events and workflows."""

    registry: dict[Event | str, WorkFlow] = Field(...)
    """ The registry of events and workflows."""

    toolboxes: Set[ToolBox] = Field(default_factory=set)

    def model_post_init(self, __context: Any) -> None:
        """Register the workflows in the role to the event bus."""
        self.resolve_configuration().register_workflows()

    def register_workflows(self) -> Self:
        """Register the workflows in the role to the event bus."""
        for event, workflow in self.registry.items():
            logger.debug(
                f"Registering workflow: `{workflow.name}` for event: `{Event.instantiate_from(event).collapse()}`"
            )
            env.on(event, workflow.serve)
        return self

    def resolve_configuration(self) -> Self:
        """Resolve the configuration of the role."""
        for workflow in self.registry.values():
            logger.debug(f"Resolving config for workflow: `{workflow.name}`")
            (
                workflow.fallback_to(self)
                .steps_fallback_to_self()
                .inject_personality(self.briefing)
                .supply_tools_from(self)
                .steps_supply_tools_from_self()
            )

        return self
