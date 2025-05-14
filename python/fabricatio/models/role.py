"""Module that contains the Role class for managing workflows and their event registrations."""

from functools import partial
from typing import Any, Callable, Dict, Self, Type

from fabricatio.emitter import env
from fabricatio.journal import logger
from fabricatio.models.action import WorkFlow
from fabricatio.models.generic import WithBriefing
from fabricatio.rust import Event
from fabricatio.utils import is_subclass_of_base
from pydantic import ConfigDict, Field

is_toolbox_usage = partial(is_subclass_of_base, base_module="fabricatio.models.usages", base_name="ToolBoxUsage")
is_scoped_config = partial(is_subclass_of_base, base_module="fabricatio.models.generic", base_name="ScopedConfig")


class Role(WithBriefing):
    """Class that represents a role with a registry of events and workflows.

    A Role serves as a container for workflows, managing their registration to events
    and providing them with shared configuration like tools and personality.
    """

    model_config = ConfigDict(use_attribute_docstrings=True, arbitrary_types_allowed=True)
    name: str = ""
    """The name of the role."""
    description: str = ""
    """A brief description of the role's responsibilities and capabilities."""

    registry: Dict[Event, WorkFlow] = Field(default_factory=dict)
    """The registry of events and workflows."""

    def model_post_init(self, __context: Any) -> None:
        """Initialize the role by resolving configurations and registering workflows.

        Args:
            __context: The context used for initialization
        """
        self.name = self.name or self.__class__.__name__

        self.resolve_configuration().register_workflows()

    def register_workflows(self) -> Self:
        """Register each workflow in the registry to its corresponding event in the event bus.

        Returns:
            Self: The role instance for method chaining
        """
        for event, workflow in self.registry.items():
            logger.debug(f"Registering workflow: `{workflow.name}` for event: `{event.collapse()}`")
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
            self._configure_scoped_config(workflow)
            self._configure_toolbox_usage(workflow)
            workflow.inject_personality(self.briefing)
        return self

    def _propagate_config(
        self,
        workflow: WorkFlow,
        has_capability: Callable[[Type], bool],
        config_method_name: str,
        capability_description: str,
    ) -> None:
        """Propagates configuration to workflow and its actions if they have a given capability."""
        if not has_capability(self.__class__):
            return

        config_source_for_actions = self
        if has_capability(workflow.__class__):
            logger.debug(
                f"Configuring {capability_description} inherited from `{self.name}` for workflow: `{workflow.name}`"
            )
            getattr(workflow, config_method_name)(self)
            config_source_for_actions = workflow

        for action in (act for act in workflow.iter_actions() if has_capability(act.__class__)):
            getattr(action, config_method_name)(config_source_for_actions)

    def _configure_scoped_config(self, workflow: WorkFlow) -> None:
        """Configure scoped configuration for workflow and its actions."""
        self._propagate_config(workflow, is_scoped_config, "fallback_to", "scoped config")

    def _configure_toolbox_usage(self, workflow: WorkFlow) -> None:
        """Configure toolbox usage for workflow and its actions."""
        self._propagate_config(workflow, is_toolbox_usage, "supply_tools_from", "toolbox usage")
