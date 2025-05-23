"""Module that contains the Role class for managing workflows and their event registrations."""

from functools import partial
from typing import Any, Callable, Dict, Self, Type

from pydantic import ConfigDict, Field

from fabricatio_core.emitter import ENV
from fabricatio_core.journal import logger
from fabricatio_core.models.action import WorkFlow
from fabricatio_core.models.generic import WithBriefing
from fabricatio_core.rust import Event
from fabricatio_core.utils import is_subclass_of_base

is_toolbox_usage = partial(is_subclass_of_base, base_module="fabricatio_core.models.usages", base_name="ToolBoxUsage")
is_scoped_config = partial(is_subclass_of_base, base_module="fabricatio_core.models.generic", base_name="ScopedConfig")


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

    registry: Dict[Event, WorkFlow] = Field(default_factory=dict, frozen=True)
    """The registry of events and workflows."""
    dispatch_on_init: bool = Field(True, frozen=True)
    """Whether to dispatch registered workflows on initialization."""

    @property
    def briefing(self) -> str:
        """Get the briefing of the role.

        Returns:
            str: The briefing of the role.
        """
        base = super().briefing

        abilities = "\n".join(f'`{k.collapse()}`:{w.briefing}' for (k, w) in self.registry.items())

        return f"{base}\n\nAbilities:\n{abilities}"

    def model_post_init(self, __context: Any) -> None:
        """Initialize the role by resolving configurations and registering workflows.

        Args:
            __context: The context used for initialization
        """
        self.name = self.name or self.__class__.__name__

        if self.dispatch_on_init:
            self.resolve_configuration().dispatch()

    def register_workflow(self, event: Event, workflow: WorkFlow) -> Self:
        """Register a workflow to the role's registry."""
        if event in self.registry:
            logger.warning(
                f"Event `{event.collapse()}` is already registered with workflow "
                f"`{self.registry[event].name}`. It will be overwritten by `{workflow.name}`."
            )
        self.registry[event] = workflow
        return self

    def unregister_workflow(self, event: Event) -> Self:
        """Unregister a workflow from the role's registry for the given event."""
        if event in self.registry:
            logger.debug(f"Unregistering workflow `{self.registry[event].name}` for event `{event.collapse()}`")
            del self.registry[event]

        else:
            logger.warning(f"No workflow registered for event `{event.collapse()}` to unregister.")
        return self

    def dispatch(self) -> Self:
        """Register each workflow in the registry to its corresponding event in the event bus.

        Returns:
            Self: The role instance for method chaining
        """
        for event, workflow in self.registry.items():
            logger.debug(f"Registering workflow: `{workflow.name}` for event: `{event.collapse()}`")
            ENV.on(event, workflow.serve)
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
            self._configure_scoped_config(workflow)._configure_toolbox_usage(workflow)

        return self

    def _propagate_config(
            self,
            workflow: WorkFlow,
            has_capability: Callable[[Type], bool],
            config_method_name: str,
            capability_description: str,
    ) -> Self:
        """Propagates configuration from the Role to a Workflow and its Actions.

        This method checks if the Role, Workflow, or its Actions possess a specific
        capability (e.g., being a ScopedConfig or ToolBoxUsage). If they do,
        a specified configuration method is called on them to apply or inherit
        settings.

        The configuration flows hierarchically:
        1. If the Role has the capability, it's the initial source.
        2. If the Workflow also has the capability, it can inherit from the Role
           and then becomes the source for its Actions.
        3. Actions with the capability inherit from the determined source (either
           Workflow or Role).

        Args:
            workflow: The WorkFlow instance to configure.
            has_capability: A callable that takes a Type and returns True if
                            the type possesses the specific capability, False otherwise.
            config_method_name: The name of the method to call on an object
                                (Role, Workflow, Action) to apply the configuration.
                                For example, "fallback_to" or "supply_tools_from".
            capability_description: A string describing the capability, used for
                                    logging purposes (e.g., "scoped config", "toolbox usage").
        """
        # This variable will hold the object from which Actions should inherit their configuration.
        # It could be the Role itself or the Workflow, depending on their capabilities.
        config_source_for_actions = None

        # Check if the Role itself has the capability.
        if has_capability(self.__class__):
            # If the Role has the capability, it becomes the initial source for configuration.
            config_source_for_actions = self

        # Check if the Workflow has the capability.
        if has_capability(workflow.__class__):
            logger.debug(
                f"Configuring {capability_description} inherited from `{self.name}` for workflow: `{workflow.name}`"
            )
            # If the Role was already identified as a config source,
            # the Workflow an inherit its configuration directly from the Role.
            if config_source_for_actions is not None:
                # Call the specified configuration method on the workflow, passing the Role (self) as the source.
                getattr(workflow, config_method_name)(config_source_for_actions)

            # After potentially inheriting from the Role, the Workflow itself becomes
            # the source of configuration for its Actions.
            config_source_for_actions = workflow

        # If a configuration source (either Role or Workflow) has been established:
        if config_source_for_actions is not None:
            # Iterate over all actions within the workflow.
            # Filter for actions that possess the specified capability.
            for action in (act for act in workflow.iter_actions() if has_capability(act.__class__)):
                # Call the specified configuration method on the action,
                # passing the determined config_source_for_actions.
                getattr(action, config_method_name)(config_source_for_actions)

        return self

    def _configure_scoped_config(self, workflow: WorkFlow) -> Self:
        """Configure scoped configuration for workflow and its actions."""
        return self._propagate_config(workflow, is_scoped_config, "fallback_to", "scoped config")

    def _configure_toolbox_usage(self, workflow: WorkFlow) -> Self:
        """Configure toolbox usage for workflow and its actions."""
        return self._propagate_config(workflow, is_toolbox_usage, "supply_tools_from", "toolbox usage")
