"""Module that contains the Role class for managing workflows and their event registrations."""

from typing import Any, Dict, List, Self, Set, Union, overload

from pydantic import ConfigDict, Field

from fabricatio_core.emitter import EMITTER
from fabricatio_core.journal import logger
from fabricatio_core.models.action import Action, WorkFlow
from fabricatio_core.models.generic import ScopedConfig, WithBriefing
from fabricatio_core.rust import Event

type RoleName = str

ROLE_REGISTRY: Dict[RoleName, "Role"] = {}


class Role(WithBriefing):
    """Class that represents a role with a registry of events and workflows.

    A Role serves as a container for workflows, managing their registration to events
    and providing them with shared configuration like tools and personality.
    """

    model_config = ConfigDict(use_attribute_docstrings=True, arbitrary_types_allowed=True)
    name: str = Field(default="")
    """The name of the role."""
    description: str = ""
    """A brief description of the role's responsibilities and capabilities."""

    skills: Dict[Event, WorkFlow] = Field(default_factory=dict, frozen=True)
    """A dictionary of event-workflow pairs."""

    dispatch_on_init: bool = Field(default=False, frozen=True)
    """Whether to dispatch registered workflows on initialization."""

    @property
    def briefing(self) -> str:
        """Get the briefing of the role.

        Returns:
            str: The briefing of the role.
        """
        base = super().briefing

        abilities = "\n".join(f"  - `{k.collapse()}` ==> {w.briefing}" for (k, w) in self.skills.items())

        return f"{base}\nEvent Mapping:\n{abilities}"

    @property
    def accept_events(self) -> List[str]:
        """Get the set of events that the role accepts.

        Returns:
            Set[Event]: The set of events that the role accepts.
        """
        return [k.collapse() for k in self.skills]

    def model_post_init(self, __context: Any) -> None:
        """Initialize the role by resolving configurations and registering workflows.

        Args:
            __context: The context used for initialization
        """
        self.name = self.name or self.__class__.__name__

        if self.dispatch_on_init:
            self.resolve_configuration().dispatch()

        register_role(self)

    def add_skill(self, event: Event, workflow: WorkFlow) -> Self:
        """Register a workflow to the role's registry."""
        if event in self.skills:
            logger.warn(
                f"Event `{event.collapse()}` is already registered with workflow "
                f"`{self.skills[event].name}`. It will be overwritten by `{workflow.name}`."
            )
        self.skills[event] = workflow
        return self

    def remove_skill(self, event: Event) -> Self:
        """Unregister a workflow from the role's registry for the given event."""
        if event in self.skills:
            logger.debug(f"Unregistering workflow `{self.skills[event].name}` for event `{event.collapse()}`")
            del self.skills[event]

        else:
            logger.warn(f"No workflow registered for event `{event.collapse()}` to unregister.")
        return self

    def dispatch(self) -> Self:
        """Register each workflow in the registry to its corresponding event in the event bus.

        Returns:
            Self: The role instance for method chaining
        """
        for event, workflow in self.skills.items():
            logger.debug(f"Registering workflow: `{workflow.name}` for event: `{event.collapse()}`")
            EMITTER.on(event.collapse(), workflow.serve)
        return self

    def undo_dispatch(self) -> Self:
        """Unregister each workflow in the registry from its corresponding event in the event bus.

        Returns:
            Self: The role instance for method chaining
        """
        for event, workflow in self.skills.items():
            logger.debug(f"Unregistering workflow: `{workflow.name}` for event: `{event.collapse()}`")
            EMITTER.off(event.collapse())
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
            self.hold_to(self.skills.values(), EXCLUDED_FIELDS)  # pyright: ignore [reportAttributeAccessIssue]
        for workflow in self.skills.values():
            if issubclass(workflow.__class__, ScopedConfig):
                logger.debug(f"Workflow `{workflow.name}` is a ScopedConfig. Applying configuration to its steps.")
                workflow.hold_to(workflow.steps, EXCLUDED_FIELDS)  # pyright: ignore [reportAttributeAccessIssue]
            elif issubclass(self.__class__, ScopedConfig):
                logger.debug(
                    f"Workflow `{workflow.name}` is not a ScopedConfig, but role `{self.name}` is. "
                    "Applying role configuration to workflow steps."
                )
                self.hold_to(workflow.steps, EXCLUDED_FIELDS)  # pyright: ignore [reportAttributeAccessIssue]
            else:
                logger.debug(
                    f"Neither role nor workflow `{workflow.name}` is a ScopedConfig. "
                    "Skipping configuration resolution for this workflow."
                )
                continue
        return self


def register_role(role: "Role", override: bool = True) -> None:
    """Register the role into the global registry."""
    if not override and role.name in ROLE_REGISTRY:
        raise ValueError(f"Role with name `{role.name}` already exists.")
    logger.debug(f"Registering role: `{role.name}`")
    ROLE_REGISTRY[role.name] = role


def unregister_role(role: Union["Role", RoleName]) -> None:
    """Unregister the role from the global registry."""
    name = role.name if isinstance(role, Role) else role
    if name not in ROLE_REGISTRY:
        raise ValueError(f"Role with name `{name}` does not exist.")
    del ROLE_REGISTRY[name]


def clear_registry() -> None:
    """Clear the global registry of all registered roles."""
    ROLE_REGISTRY.clear()


@overload
def get_registered_role(role_name: RoleName) -> Role: ...


@overload
def get_registered_role(role_name: Set[RoleName]) -> List[Role]: ...


def get_registered_role(role_name: RoleName | Set[RoleName]) -> Role | List[Role]:
    """Get a registered role by name."""
    return ROLE_REGISTRY[role_name] if isinstance(role_name, str) else [ROLE_REGISTRY[r] for r in role_name]


EXCLUDED_FIELDS = set(
    list(Role.model_fields.keys()) + list(WorkFlow.model_fields.keys()) + list(Action.model_fields.keys())
)
"""The set of fields that should not be resolved during configuration resolution."""
