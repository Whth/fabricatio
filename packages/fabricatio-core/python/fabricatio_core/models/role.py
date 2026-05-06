"""Module that contains the Role class for managing workflows and their event registrations."""

from typing import Any, Callable, Dict, List, Optional, Self, Set, TypedDict, Union, Unpack, overload

from pydantic import ConfigDict, Field, PrivateAttr

from fabricatio_core.emitter import EMITTER
from fabricatio_core.journal import logger
from fabricatio_core.models.action import Action, WorkFlow
from fabricatio_core.models.generic import ScopedConfig, WithBriefing
from fabricatio_core.rust import Event
from fabricatio_core.utils import first_available

type RoleName = str
type EventPattern = str

ROLE_REGISTRY: Dict[RoleName, "Role"] = {}


class Role(WithBriefing):
    """Class that represents a role with a registry of events and workflows.

    A Role serves as a container for workflows, managing their registration to events
    and providing them with shared configuration like tools and personality.
    """

    model_config = ConfigDict(use_attribute_docstrings=True)
    name: RoleName = Field(default="")
    """The name of the role."""
    description: str = ""
    """A brief description of the role's responsibilities and capabilities."""

    subscriptions: Dict[EventPattern, WorkFlow] = Field(default_factory=dict, frozen=True)
    """A dictionary of event-workflow pairs."""

    _dispatched: bool = PrivateAttr(default=False)
    """A flag indicating whether the role has been dispatched."""

    @classmethod
    def new(
        cls,
        subscriptions: Dict[EventPattern, WorkFlow],
        /,
        name: Optional[RoleName] = None,
        description: str = "",
        dispatch_on_init: bool = False,
        **kwargs: Unpack[TypedDict],
    ) -> Self:
        """Create a new Role."""
        real_name = first_available((name, cls.__name__))

        self = cls(name=real_name, description=description, subscriptions=subscriptions, **kwargs)

        return self.dispatch() if dispatch_on_init else self

    @classmethod
    def with_bio(
        cls,
        name: Optional[RoleName] = None,
        description: str = "",
    ) -> Self:
        """Create a new Role with a bio."""
        return cls.new({}, name=name, description=description)

    @classmethod
    def with_subscriptions(cls, subscriptions: Dict[EventPattern, WorkFlow]) -> Self:
        """Create a new Role with subscription specified only."""
        return cls.new(subscriptions)

    @property
    def briefing(self) -> str:
        """Get the briefing of the role.

        Returns:
            str: The briefing of the role.
        """
        base = super().briefing

        abilities = "\n".join(f"  - `{k}` ==> {w.briefing}" for (k, w) in self.subscriptions.items())

        return f"{base}\nEvent Mapping:\n{abilities}"

    @property
    def accept_events(self) -> List[str]:
        """Get the set of events that the role accepts.

        Returns:
            Set[Event]: The set of events that the role accepts.
        """
        return list(self.subscriptions.keys())

    def model_post_init(self, __context: Any) -> None:
        """Register the role."""
        register_role(self)

    @overload
    def configure(self, /, **kwargs) -> Self: ...
    @overload
    def configure(self, fn: Callable[[Self], None]) -> Self: ...
    def configure(self, fn: Optional[Callable[[Self], None]] = None, /, **kwargs) -> Self:
        """Configure the role."""
        if fn:
            fn(self)
            return self
        for k, v in kwargs.items():
            if not hasattr(self, k):
                raise KeyError(f"{self.__class__.__name__} has no attribute {k}")
            setattr(self, k, v)
        return self

    def subscribe(self, event: Event | EventPattern, workflow: WorkFlow) -> Self:
        """Register a workflow to the role's registry."""
        event_string = event.collapse() if isinstance(event, Event) else event

        if event_string in self.subscriptions:
            logger.warn(
                f"Event `{event_string}` is already registered with workflow "
                f"`{self.subscriptions[event_string].name}`. It will be overwritten by `{workflow.name}`."
            )
        self.subscriptions[event_string] = workflow
        return self

    def unsubscribe(self, event: Event | EventPattern) -> Self:
        """Unregister a workflow from the role's registry for the given event."""
        event_string = event.collapse() if isinstance(event, Event) else event

        if event_string in self.subscriptions:
            logger.debug(f"Unregistering workflow `{self.subscriptions[event_string].name}` for event `{event_string}`")
            del self.subscriptions[event_string]

        else:
            logger.warn(f"No workflow registered for event `{event_string}` to unregister.")
        return self

    def dispatch(self, resolve_config: bool = True) -> Self:
        """Register each workflow in the registry to its corresponding event in the event bus.

        Returns:
            Self: The role instance for method chaining
        """
        if self._dispatched:
            logger.warn("Role already dispatched. Skipping dispatch.")
            return self

        if resolve_config:
            self.resolve_configuration()

        for event, workflow in self.subscriptions.items():
            logger.debug(f"Registering workflow: `{workflow.name}` for event: `{event}`")
            EMITTER.on(event, workflow.serve)
        self._dispatched = True
        return self

    def undo_dispatch(self) -> Self:
        """Unregister each workflow in the registry from its corresponding event in the event bus.

        Returns:
            Self: The role instance for method chaining
        """
        if not self._dispatched:
            logger.warn("Not dispatched, nothing to undo.")
            return self

        for event, workflow in self.subscriptions.items():
            logger.debug(f"Unregistering workflow: `{workflow.name}` for event: `{event}`")
            EMITTER.off(event)
        self._dispatched = False
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
            self.hold_to(self.subscriptions.values(), EXCLUDED_FIELDS)  # pyright: ignore [reportAttributeAccessIssue]
        for workflow in self.subscriptions.values():
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
