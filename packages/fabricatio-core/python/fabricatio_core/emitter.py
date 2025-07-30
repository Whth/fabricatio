"""Core module that contains the Env class for managing event handling."""

from dataclasses import dataclass
from typing import Callable, ClassVar, Optional, Self, overload

from pymitter import EventEmitter

from fabricatio_core.rust import CONFIG, Event


@dataclass
class Env:
    """Environment class that manages event handling using EventEmitter.

    This class provides methods for registering event listeners, emitting events,
    and handling asynchronous operations related to event management.

    Attributes:
        ee (ClassVar[EventEmitter]): The underlying EventEmitter instance used for
            managing events. Initialized with configuration settings including
            delimiter, new listener event, maximum listeners, and wildcard support.

    Example:
        .. code-block:: python
            # Register an event listener
            def my_handler(data):
                print(f"Received: {data}")

            env = Env()
            env.on("my_event", my_handler)

            # Emit an event
            env.emit("my_event", "Hello World")
    """

    ee: ClassVar[EventEmitter] = EventEmitter(
        delimiter=CONFIG.pymitter.delimiter,
        new_listener=CONFIG.pymitter.new_listener_event,
        max_listeners=CONFIG.pymitter.max_listeners,
        wildcard=True,
    )

    @overload
    def on[**P, R](self, event: str | Event,func: Callable[P, R], /, ttl: int = -1) -> Self:
        """
        Registers an event listener that listens indefinitely or for a specified number of times.

        Args:
            event: The event to listen for. Can be a string or Event enum.
            func: The function to be called when the event is emitted.
            ttl: Time-to-live for the listener. If -1 (default), the listener will 
                listen indefinitely. Otherwise, it will be removed after `ttl` emissions.

        Returns:
            Self: The current instance of Env for method chaining.

        Raises:
            TypeError: If the event type is not supported.

        Example:
            .. code-block:: python

                # Listen for an event indefinitely
                env.on("user_login", handle_login)

                # Listen for an event only 3 times
                env.on("data_update", handle_update, ttl=3)
        """
        ...

    @overload
    def on[**P, R](
        self,
        event: str | Event,
        func: None = None,
        /,
        ttl: int = -1,
    ) -> Callable[[Callable[P, R]], Callable[P, R]]:
        """
        Decorator form of on() that registers an event listener with a specific function.

        Args:
            event: The event to listen for. Can be a string or Event enum.
            func: Must be None when using as a decorator.
            ttl: Time-to-live for the listener. If -1 (default), the listener will 
                listen indefinitely. Otherwise, it will be removed after `ttl` emissions.

        Returns:
            A decorator that registers the decorated function as an event listener.

        Example:
            .. code-block:: python
                @env.on("user_login")
                def handle_login(user_data):
                    print(f"User {user_data} logged in")
        """
        ...

    def on[**P, R](
        self,
        event: str | Event,
        func: Optional[Callable[P, R]] = None,
        /,
        ttl=-1,
    ) -> Callable[[Callable[P, R]], Callable[P, R]] | Self:
        """Registers an event listener that listens indefinitely or for a specified number of times.

        This method can be used either as a direct function call or as a decorator.
        
        Args:
            event: The event to listen for. Can be a string or Event enum.
            func: The function to be called when the event is emitted. If None, 
                the method acts as a decorator.
            ttl: Time-to-live for the listener. If -1 (default), the listener will 
                listen indefinitely. Otherwise, it will be removed after `ttl` emissions.

        Returns:
            Either a decorator function (when func is None) or the current Env instance.

        Raises:
            TypeError: If the event type is not supported.

        Example:
            .. code-block:: python
                # Direct usage
                env.on("user_login", handle_login)

                # Decorator usage
                @env.on("user_login")
                def handle_login(user_data):
                    print(f"User {user_data} logged in")
        """
        if isinstance(event, Event):
            event = event.collapse()
        if func is None:
            return self.ee.on(event, ttl=ttl)
        self.ee.on(event, func, ttl=ttl)
        return self

    @overload
    def once[**P, R](
        self,
        event: str | Event,
    ) -> Callable[[Callable[P, R]], Callable[P, R]]:
        """
        Decorator form that registers an event listener that listens only once.

        Args:
            event: The event to listen for. Can be a string or Event enum.

        Returns:
            A decorator that registers the decorated function as a one-time event listener.

        Example:
            .. code-block:: python
                @env.once("app_ready")
                def initialize_app():
                    print("App initialized - this will only run once")
        """
        ...

    @overload
    def once[**P, R](
        self,
        event: str | Event,
        func: Callable[P, R],
    ) -> Self:
        """
        Registers an event listener with a specific function that listens only once.

        Args:
            event: The event to listen for. Can be a string or Event enum.
            func: The function to be called when the event is emitted.

        Returns:
            Self: The current instance of Env for method chaining.

        Example:
            .. code-block:: python
                env.once("app_ready", initialize_app)
        """
        ...

    def once[**P, R](
        self,
        event: str | Event,
        func: Optional[Callable[P, R]] = None,
    ) -> Callable[[Callable[P, R]], Callable[P, R]] | Self:
        """Registers an event listener that listens only once.

        This method can be used either as a direct function call or as a decorator.
        After the event is emitted once, the listener is automatically removed.

        Args:
            event: The event to listen for. Can be a string or Event enum.
            func: The function to be called when the event is emitted. If None, 
                the method acts as a decorator.

        Returns:
            Either a decorator function (when func is None) or the current Env instance.

        Example:
            .. code-block:: python
                # Direct usage
                env.once("app_ready", initialize_app)

                # Decorator usage
                @env.once("app_ready")
                def initialize_app():
                    print("App initialized - this will only run once")
        """
        if isinstance(event, Event):
            event = event.collapse()
        if func is None:
            return self.ee.once(event)

        self.ee.once(event, func)
        return self

    def emit[**P](self, event: str | Event, *args: P.args, **kwargs: P.kwargs) -> None:
        """Emits an event to all registered listeners.

        All listeners registered for this event will be called synchronously
        with the provided arguments.

        Args:
            event: The event to emit. Can be a string or Event enum.
            *args: Positional arguments to pass to the listeners.
            **kwargs: Keyword arguments to pass to the listeners.

        Raises:
            TypeError: If the event type is not supported.

        Example:
            .. code-block:: python
                env.emit("user_login", user_id=123, username="john_doe")
        """
        if isinstance(event, Event):
            event = event.collapse()

        self.ee.emit(event, *args, **kwargs)

    async def emit_async[**P](self, event: str | Event, *args: P.args, **kwargs: P.kwargs) -> None:
        """Asynchronously emits an event to all registered listeners.

        All listeners registered for this event will be called asynchronously
        with the provided arguments.

        Args:
            event: The event to emit. Can be a string or Event enum.
            *args: Positional arguments to pass to the listeners.
            **kwargs: Keyword arguments to pass to the listeners.

        Raises:
            TypeError: If the event type is not supported.

        Example:
            .. code-block:: python
                await env.emit_async("data_processed", result=data)
        """
        if isinstance(event, Event):
            event = event.collapse()
        return await self.ee.emit_async(event, *args, **kwargs)

    def emit_future[**P](self, event: str | Event, *args: P.args, **kwargs: P.kwargs) -> None:
        """Emits an event and returns a future object for async processing.

        This method emits the event and returns a future that can be awaited
        for completion of all listeners.

        Args:
            event: The event to emit. Can be a string or Event enum.
            *args: Positional arguments to pass to the listeners.
            **kwargs: Keyword arguments to pass to the listeners.

        Returns:
            A future object representing the completion of all listeners.

        Raises:
            TypeError: If the event type is not supported.

        Example:
            .. code-block:: python
                future = env.emit_future("long_running_task", task_data)
                # ... do other work ...
                await future  # Wait for all listeners to complete
        """
        if isinstance(event, Event):
            event = event.collapse()
        return self.ee.emit_future(event, *args, **kwargs)


ENV = Env()

__all__ = ["ENV"]
