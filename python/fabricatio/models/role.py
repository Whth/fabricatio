"""Module that contains the Role class for managing workflows and their event registrations."""

from typing import Any, Self, Set

from fabricatio.capabilities.correct import Correct
from fabricatio.capabilities.task import HandleTask, ProposeTask
from fabricatio.core import env
from fabricatio.journal import logger
from fabricatio.models.action import WorkFlow
from fabricatio.models.events import Event
from fabricatio.models.generic import WithBriefing
from fabricatio.models.tool import ToolBox
from pydantic import Field


class Role(WithBriefing, ProposeTask, HandleTask, Correct):
    """Class that represents a role with a registry of events and workflows.

    A Role serves as a container for workflows, managing their registration to events
    and providing them with shared configuration like tools and personality.

    Attributes:
        registry: Mapping of events to workflows that handle them
        toolboxes: Set of toolboxes available to this role and its workflows
    """
    description:str =""
    """A brief description of the role's responsibilities and capabilities."""

    registry: dict[Event | str, WorkFlow] = Field(default_factory=dict)
    """The registry of events and workflows."""

    toolboxes: Set[ToolBox] = Field(default_factory=set)
    """Collection of tools available to this role."""

    def model_post_init(self, __context: Any) -> None:
        """Initialize the role by resolving configurations and registering workflows.

        Args:
            __context: The context used for initialization
        """
        self.resolve_configuration().register_workflows()

    def register_workflows(self) -> Self:
        """Register each workflow in the registry to its corresponding event in the event bus.

        Returns:
            Self: The role instance for method chaining
        """
        for event, workflow in self.registry.items():
            logger.debug(
                f"Registering workflow: `{workflow.name}` for event: `{Event.instantiate_from(event).collapse()}`"
            )
            env.on(event, workflow.serve)
        return self

    def resolve_configuration(self) -> Self:
        """Apply role-level configuration to all workflows in the registry.

        This includes setting up fallback configurations, injecting personality traits,
        and providing tool access to workflows and their steps.

        Returns:
            Self: The role instance for method chaining
        """
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
