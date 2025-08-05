"""Core module that contains the Env class for managing event handling."""

import asyncio
from asyncio import as_completed
from asyncio.tasks import Task
from collections import defaultdict
from typing import TYPE_CHECKING, Callable, Coroutine, Dict, List, Self, Tuple

from fabricatio_core.rust import CONFIG

if TYPE_CHECKING:
    from fabricatio_core.models.task import Task as _Task

WILDCARD = "*"


type Callback[T] = Callable[[T], Coroutine[None, None, None]]
"""Callback type for event handlers."""


class EventEmitter[T]:
    """An event emitter that supports both exact and wildcard event matching.

    The emitter allows registering event handlers for specific events or patterns
    containing wildcards (`*`). It can then emit events and invoke all matching handlers
    concurrently.
    """

    def __init__(self, sep: str = "::") -> None:
        """Creates a new EventEmitter with the specified separator.

        Args:
            sep: The separator string used to split event names into segments.
                 Defaults to "::".
        """
        self.sep = sep
        # Stores handlers for exact event matches (key: event name, value: list of callbacks)
        self._handlers: Dict[str, List[Callback[T]]] = defaultdict(list)
        # Stores handlers for wildcard event patterns (key: pattern tuple, value: list of callbacks)
        self._wildcard_handlers: Dict[Tuple[str, ...], List[Callback[T]]] = defaultdict(list)

    def on(self, pattern: str, callback: Callback[T]) -> Self:
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

        parts = pattern.split(self.sep)
        if any(part == WILDCARD for part in parts):
            # Use tuple as key for hashability
            self._wildcard_handlers[tuple(parts)].append(callback)
        else:
            self._handlers[pattern].append(callback)
        return self

    def off(self, pattern: str) -> Self:
        """Removes an event handler for a specific pattern.

        The pattern must match the pattern used when registering the handler.

        Args:
            pattern: The event pattern to remove the handler for.

        Raises:
            ValueError: If the pattern is empty.
        """
        if not pattern:
            raise ValueError("Pattern cannot be empty")

        parts = pattern.split(self.sep)
        if any(part == WILDCARD for part in parts):
            self._wildcard_handlers.pop(tuple(parts))
        else:
            self._handlers.pop(pattern)
        return self

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

    async def emit(self, event: str, data: T) -> None:
        """Emits an event with the given data to all matching handlers.

        This method finds all handlers that match the event pattern (both exact
        and wildcard matches) and invokes them concurrently with the provided data.

        Args:
            event: The name of the event to emit.
            data: The data to pass to the event handlers.

        Note:
            The execution of the event handlers is concurrent, and this method
            will wait for all handlers to complete before returning.
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
            for cro in as_completed([callback(data) for callback in callbacks]):
                await cro

    def emit_future(self, event: str, data: T) -> Task:
        """Emits an event with the given data to all matching handlers.

        This method finds all handlers that match the event pattern (both exact
        and wildcard matches) and invokes them concurrently with the provided data.

        Args:
            event: The name of the event to emit.
            data: The data to pass to the event handlers.

        Returns:
            A future that will be completed when all handlers have been invoked.
        """
        return asyncio.ensure_future(self.emit(event, data))


EMITTER: EventEmitter["_Task"] = EventEmitter(sep=CONFIG.emitter.delimiter)
"""The global event emitter instance."""
