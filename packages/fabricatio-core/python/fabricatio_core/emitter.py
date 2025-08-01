"""Core module that contains the Env class for managing event handling."""

import asyncio
from collections import defaultdict
from typing import Any, Callable, Coroutine, Dict, List, Tuple

from fabricatio_core.rust import CONFIG

WILDCARD = "*"


class PatternType:
    """Base class for pattern types."""


class Exact(PatternType):
    """Represents an exact pattern match."""

    def __init__(self, value: str) -> None:
        self.value = value

    def __repr__(self) -> str:
        return f"Exact({self.value})"


class Wildcard(PatternType):
    """Represents a wildcard pattern match."""

    def __init__(self, segments: List[str]) -> None:
        self.segments = segments

    def __repr__(self) -> str:
        return f"Wildcard({self.segments})"


def pattern_type_from_string(source: str, sep: str) -> PatternType:
    """Creates a PatternType from a string by splitting it with a separator.

    Args:
        source: The string to split.
        sep: The separator used to split the string.

    Returns:
        A PatternType instance (Exact or Wildcard).
    """
    parts = source.split(sep)
    if any(part == WILDCARD for part in parts):
        return Wildcard(parts)
    # For Exact, we store the original string, not the concatenated parts
    # to match the Rust behavior for handler lookup.
    return Exact(source)  # Or Exact('.'.join(parts)) if you want the joined key


type Callback[T] = Callable[[T], Coroutine[None, None, None]]


class EventEmitter[T]:
    """An event emitter that supports both exact and wildcard event matching.

    The emitter allows registering event handlers for specific events or patterns
    containing wildcards (`*`). It can then emit events and invoke all matching handlers
    concurrently.
    """

    def __init__(self, sep: str = ".") -> None:
        """Creates a new EventEmitter with the specified separator.

        Args:
            sep: The separator string used to split event names into segments.
                 Defaults to ".".
        """
        self.sep = sep
        # Stores handlers for exact event matches (key: event name, value: list of callbacks)
        self._handlers: Dict[str, List[Callback[T]]] = defaultdict(list)
        # Stores handlers for wildcard event patterns (key: pattern tuple, value: list of callbacks)
        self._wildcard_handlers: Dict[Tuple[str, ...], List[Callback[T]]] = defaultdict(list)

    def on(self, pattern: str, callback: Callback[T]) -> None:
        """Registers an event handler for a specific pattern.

        The pattern can be an exact event name or contain wildcards (`*`) to match
        multiple events. The callback will be invoked whenever an event matching
        the pattern is emitted.

        Args:
            pattern: The event pattern to register the handler for.
            callback: The async callback function to invoke. It must be a coroutine
                      function or return a Future/Task.

        Raises:
            ValueError: If the pattern is empty.
        """
        if not pattern:
            raise ValueError("Pattern cannot be empty")

        pattern_type = pattern_type_from_string(pattern, self.sep)

        if isinstance(pattern_type, Exact):
            self._handlers[pattern_type.value].append(callback)
        elif isinstance(pattern_type, Wildcard):
            # Use tuple as key for hashability
            key = tuple(pattern_type.segments)
            self._wildcard_handlers[key].append(callback)

    def _gather_exact_handlers(self, event_parts: List[str]) -> List[Callback[T]]:
        """Gathers all exact handlers that match the given event parts."""
        event_name = self.sep.join(event_parts)
        return self._handlers.get(event_name, [])

    def _gather_wildcard_handlers(self, event_parts: List[str]) -> List[Callback[T]]:
        """Gathers all wildcard handlers that match the given event parts."""
        matching_handlers = []
        event_tuple = tuple(event_parts)

        for pattern_tuple, handlers in self._wildcard_handlers.items():
            # Length must match
            if len(pattern_tuple) == len(event_tuple) and all(
                p_segment in (WILDCARD, e_segment)
                for p_segment, e_segment in zip(pattern_tuple, event_tuple, strict=False)
            ):
                matching_handlers.extend(handlers)
        return matching_handlers

    async def emit(self, event: str, data: Any = None) -> None:
        """Emits an event with the given data to all matching handlers.

        This method finds all handlers that match the event pattern (both exact
        and wildcard matches) and invokes them concurrently with the provided data.

        Args:
            event: The name of the event to emit.
            data: The data to pass to the event handlers.
        """
        parts = event.split(self.sep)
        callbacks: List[Callback[T]] = []

        # Gather exact match handlers
        callbacks.extend(self._gather_exact_handlers(parts))

        # Gather wildcard match handlers (only if there are parts to match against)
        if len(parts) > 0:
            callbacks.extend(self._gather_wildcard_handlers(parts))

        # Run all gathered callbacks concurrently
        if callbacks:
            # Ensure the callback is a coroutine before awaiting
            await asyncio.gather(*[callback(data) for callback in callbacks])

    def emit_future(self, event: str, data: Any = None) -> None:
        """Emits an event with the given data to all matching handlers.

        This method finds all handlers that match the event pattern (both exact
        and wildcard matches) and invokes them concurrently with the provided data.

        Args:
            event: The name of the event to emit.
            data: The data to pass to the event handlers.
        """
        asyncio.ensure_future(self.emit(event, data))  # noqa: RUF006


EMITTER = EventEmitter(sep=CONFIG.emitter.delimiter)

__all__ = ["EMITTER"]
