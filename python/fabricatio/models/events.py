"""The module containing the Event class."""

from typing import List, Self, Union

from fabricatio.config import configs
from pydantic import BaseModel, ConfigDict, Field

type EventLike = Union[str, List[str], "Event"]


class Event(BaseModel):
    """A class representing an event."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    segments: List[str] = Field(default_factory=list, frozen=True)
    """ The segments of the namespaces."""

    @classmethod
    def instantiate_from(cls, event: EventLike) -> Self:
        """Create an Event instance from a string or list of strings or an Event instance.

        Args:
            event (EventLike): The event to instantiate from.

        Returns:
            Event: The Event instance.
        """
        if isinstance(event, Event):
            return event.clone()
        if isinstance(event, str):
            event = event.split(configs.pymitter.delimiter)

        return cls(segments=event)

    def derive(self, event: EventLike) -> Self:
        """Derive a new event from this event and another event or a string."""
        return self.clone().concat(event)

    def collapse(self) -> str:
        """Collapse the event into a string."""
        return configs.pymitter.delimiter.join(self.segments)

    def clone(self) -> Self:
        """Clone the event."""
        return Event(segments=list(self.segments))

    def push(self, segment: str) -> Self:
        """Push a segment to the event."""
        if not segment:
            raise ValueError("The segment must not be empty.")
        if configs.pymitter.delimiter in segment:
            raise ValueError("The segment must not contain the delimiter.")

        self.segments.append(segment)
        return self

    def push_wildcard(self) -> Self:
        """Push a wildcard segment to the event."""
        return self.push("*")

    def pop(self) -> str:
        """Pop a segment from the event."""
        return self.segments.pop()

    def clear(self) -> Self:
        """Clear the event."""
        self.segments.clear()
        return self

    def concat(self, event: EventLike) -> Self:
        """Concatenate another event to this event."""
        self.segments.extend(Event.instantiate_from(event).segments)
        return self

    def __hash__(self) -> int:
        """Return the hash of the event, using the collapsed string."""
        return hash(self.collapse())

    def __eq__(self, other: str | List[str] | Self) -> bool:
        """Check if the event is equal to another event or a string."""
        return self.collapse() == Event.instantiate_from(other).collapse()
