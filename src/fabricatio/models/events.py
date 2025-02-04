from typing import List, Self

from pydantic import BaseModel, ConfigDict, Field


class Event(BaseModel):
    model_config = ConfigDict(use_attribute_docstrings=True)
    delimiter: str = Field(default=".", frozen=True)
    """ The delimiter used to separate the event name into segments."""

    segments: List[str] = Field(default_factory=list, frozen=True)
    """ The segments of the namespaces."""

    @classmethod
    def from_string(cls, event: str, delimiter: str = ".") -> Self:
        """
        Create an Event instance from a string.

        Args:
            event (str): The event string.
            delimiter (str): The delimiter used to separate the event name into segments.

        Returns:
            Event: The Event instance.
        """
        return cls(delimiter=delimiter, segments=event.split(delimiter))

    def collapse(self) -> str:
        """
        Collapse the event into a string.
        """
        return self.delimiter.join(self.segments)

    def clone(self) -> Self:
        """
        Clone the event.
        """
        return Event(delimiter=self.delimiter, segments=[segment for segment in self.segments])

    def push(self, segment: str) -> Self:
        """
        Push a segment to the event.
        """
        assert segment, "The segment must not be empty."
        assert self.delimiter not in segment, "The segment must not contain the delimiter."

        self.segments.append(segment)
        return self

    def pop(self) -> str:
        """
        Pop a segment from the event.
        """
        return self.segments.pop()

    def clear(self) -> Self:
        """
        Clear the event.
        """
        self.segments.clear()
        return self

    def concat(self, event: Self) -> Self:
        """
        Concatenate another event to this event.
        """
        self.segments.extend(event.segments)
        return self
