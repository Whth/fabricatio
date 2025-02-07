from typing import Callable, Self, overload

from pydantic import BaseModel, ConfigDict, PrivateAttr
from pymitter import EventEmitter

from fabricatio.config import configs
from fabricatio.models.events import Event


class Env(BaseModel):
    """
    Environment class that manages event handling using EventEmitter.

    Attributes:
        _ee (EventEmitter): Private attribute for event handling.
    """

    model_config = ConfigDict(use_attribute_docstrings=True)
    _ee: EventEmitter = PrivateAttr(
        default_factory=lambda: EventEmitter(
            delimiter=configs.pymitter.delimiter,
            new_listener=configs.pymitter.new_listener_event,
            max_listeners=configs.pymitter.max_listeners,
            wildcard=True,
        )
    )

    @overload
    def on(self, event: str | Event, /, ttl: int = -1) -> Self:
        """
        Registers an event listener that listens indefinitely or for a specified number of times.

        Args:
            event (str | Event): The event to listen for.
            ttl (int): Time-to-live for the listener. If -1, the listener will listen indefinitely.

        Returns:
            Self: The current instance of Env.
        """
        ...

    @overload
    def on[**P, R](
        self,
        event: str | Event,
        func: Callable[P, R] = None,
        /,
        ttl: int = -1,
    ) -> Callable[[Callable[P, R]], Callable[P, R]]:
        """
        Registers an event listener with a specific function that listens indefinitely or for a specified number of times.

        Args:
            event (str | Event): The event to listen for.
            func (Callable[P, R]): The function to be called when the event is emitted.
            ttl (int): Time-to-live for the listener. If -1, the listener will listen indefinitely.

        Returns:
            Callable[[Callable[P, R]], Callable[P, R]]: A decorator that registers the function as an event listener.
        """
        ...

    def on[**P, R](
        self,
        event: str | Event,
        func: Callable[P, R] = None,
        /,
        ttl=-1,
    ) -> Callable[[Callable[P, R]], Callable[P, R]] | Self:
        """
        Registers an event listener with a specific function that listens indefinitely or for a specified number of times.
        Args:
            event (str | Event): The event to listen for.
            func (Callable[P, R]): The function to be called when the event is emitted.
            ttl (int): Time-to-live for the listener. If -1, the listener will listen indefinitely.

        Returns:
            Callable[[Callable[P, R]], Callable[P, R]] | Self: A decorator that registers the function as an event listener or the current instance of Env.
        """
        if isinstance(event, Event):
            event = event.collapse()
        if func is None:
            return self._ee.on(event, ttl=ttl)

        else:
            self._ee.on(event, func, ttl=ttl)
            return self

    @overload
    def once[**P, R](
        self,
        event: str | Event,
    ) -> Callable[[Callable[P, R]], Callable[P, R]]:
        """
        Registers an event listener that listens only once.

        Args:
            event (str | Event): The event to listen for.

        Returns:
            Callable[[Callable[P, R]], Callable[P, R]]: A decorator that registers the function as an event listener.
        """
        ...

    @overload
    def once[**P, R](
        self,
        event: str | Event,
        func: Callable[[Callable[P, R]], Callable[P, R]],
    ) -> Self:
        """
        Registers an event listener with a specific function that listens only once.

        Args:
            event (str | Event): The event to listen for.
            func (Callable[P, R]): The function to be called when the event is emitted.

        Returns:
            Self: The current instance of Env.
        """
        ...

    def once[**P, R](
        self,
        event: str | Event,
        func: Callable[P, R] = None,
    ) -> Callable[[Callable[P, R]], Callable[P, R]] | Self:
        """

        Args:
            event (str | Event): The event to listen for.
            func (Callable[P, R]): The function to be called when the event is emitted.

        Returns:
            Callable[[Callable[P, R]], Callable[P, R]] | Self: A decorator that registers the function as an event listener or the current instance
        """
        if isinstance(event, Event):
            event = event.collapse()
        if func is None:
            return self._ee.once(event)

        else:
            self._ee.once(event, func)
            return self

    def emit[**P](self, event: str | Event, *args: P.args, **kwargs: P.kwargs) -> None:
        """
        Emits an event to all registered listeners.

        Args:
            event (str | Event): The event to emit.
            *args: Positional arguments to pass to the listeners.
            **kwargs: Keyword arguments to pass to the listeners.
        """
        if isinstance(event, Event):
            event = event.collapse()

        self._ee.emit(event, *args, **kwargs)

    async def emit_async[**P](self, event: str | Event, *args: P.args, **kwargs: P.kwargs) -> None:
        """
        Asynchronously emits an event to all registered listeners.

        Args:
            event (str | Event): The event to emit.
            *args: Positional arguments to pass to the listeners.
            **kwargs: Keyword arguments to pass to the listeners.
        """
        if isinstance(event, Event):
            event = event.collapse()
        return await self._ee.emit_async(event, *args, **kwargs)


env = Env()
