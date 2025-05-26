"""Module that contains the Role class for managing workflows and their event registrations."""

from functools import partial
from typing import Any, Dict, Self

from pydantic import ConfigDict, Field

from fabricatio_core.emitter import ENV
from fabricatio_core.journal import logger
from fabricatio_core.models.action import Action, WorkFlow
from fabricatio_core.models.generic import ScopedConfig, WithBriefing
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
    dispatch_on_init: bool = Field(default=True, frozen=True)
    """Whether to dispatch registered workflows on initialization."""

    @property
    def briefing(self) -> str:
        """Get the briefing of the role.

        Returns:
            str: The briefing of the role.
        """
        base = super().briefing

        abilities = "\n".join(f"`{k.collapse()}`:{w.briefing}" for (k, w) in self.registry.items())

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
        """Resolve and bind shared configuration to workflows and their components.

        This method ensures that any shared configuration from the role or workflows
        is properly propagated to the workflow steps and nested components. If the role
        is a ScopedConfig, it holds configuration for all workflows. Similarly, if a
        workflow itself is a ScopedConfig, it holds configuration for its own steps.

        Returns:
            Self: The role instance with resolved configurations.
        """
        if issubclass(self.__class__, ScopedConfig):
            logger.debug(f"Role `{self.name}` is a ScopedConfig. Applying configuration to all workflows.")
            self.hold_to(self.registry.values(), EXCLUDED_FIELDS)
        for workflow in self.registry.values():
            if issubclass(workflow.__class__, ScopedConfig):
                logger.debug(f"Workflow `{workflow.name}` is a ScopedConfig. Applying configuration to its steps.")
                workflow.hold_to(workflow.steps, EXCLUDED_FIELDS)
            elif issubclass(self.__class__, ScopedConfig):
                logger.debug(
                    f"Workflow `{workflow.name}` is not a ScopedConfig, but role `{self.name}` is. "
                    "Applying role configuration to workflow steps."
                )
                self.hold_to(workflow.steps, EXCLUDED_FIELDS)
            else:
                logger.debug(
                    f"Neither role nor workflow `{workflow.name}` is a ScopedConfig. "
                    "Skipping configuration resolution for this workflow."
                )
                continue
        return self


EXCLUDED_FIELDS = set(
    list(Role.model_fields.keys()) + list(WorkFlow.model_fields.keys()) + list(Action.model_fields.keys())
)
