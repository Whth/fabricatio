"""This module defines the `Task` class, which represents a task with a status and output.

It includes methods to manage the task's lifecycle, such as starting, finishing, cancelling, and failing the task.
"""

from asyncio import Queue, run
from typing import Any, Dict, List, Optional, Self, Union

from pydantic import Field, PrivateAttr

from fabricatio_core.emitter import ENV
from fabricatio_core.journal import logger
from fabricatio_core.models.generic import ProposedAble, WithBriefing, WithDependency
from fabricatio_core.rust import CONFIG, TEMPLATE_MANAGER, Event, TaskStatus

type EventLike = Union[str, Event, List[str]]


class Task[T](WithBriefing, ProposedAble, WithDependency):
    """A class representing a task with a status and output.

    Attributes:
        name (str): The name of the task.
        description (str): The description of the task.
        goals (str): The goal of the task.
        dependencies (List[str]): The file dependencies of the task, a list of file paths.
        namespace (List[str]): The namespace of the task, a list of namespace segment, as string.
    """

    name: str = Field(...)
    """The name of the task, which should be concise and descriptive."""

    description: str = Field(default="")
    """A detailed explanation of the task that includes all necessary information. Should be clear and answer what, why, when, where, who, and how questions."""

    goals: List[str] = Field(default_factory=list)
    """A list of objectives that the task aims to accomplish. Each goal should be clear and specific. Complex tasks should be broken into multiple smaller goals."""

    namespace: List[str] = Field(default_factory=list)
    """A list of string segments that identify the task's location in the system. If not specified, defaults to an empty list."""

    dependencies: List[str] = Field(default_factory=list)
    """A list of file paths that are needed or mentioned in the task's description (either reading or writing) to complete this task. If not specified, defaults to an empty list."""

    _output: Queue[T | None] = PrivateAttr(default_factory=Queue)
    """The output queue of the task."""

    _status: TaskStatus = PrivateAttr(default=TaskStatus.Pending)
    """The status of the task."""

    _namespace: Event = PrivateAttr(default_factory=Event)
    """The namespace of the task as an event, which is generated from the namespace list."""
    _extra_init_context: Dict = PrivateAttr(default_factory=dict)
    """Extra initialization context for the task, which is designed to override the one of the Workflow."""

    @property
    def extra_init_context(self) -> Dict:
        """Extra initialization context for the task, which is designed to override the one of the Workflow."""
        return self._extra_init_context

    def update_init_context(self, /, **kwargs) -> Self:
        """Update the extra initialization context for the task."""
        self.extra_init_context.update(kwargs)
        return self

    def model_post_init(self, __context: Any) -> None:
        """Initialize the task with a namespace event."""
        self._namespace.concat(self.namespace)

    def move_to(self, new_namespace: EventLike) -> Self:
        """Move the task to a new namespace.

        Args:
            new_namespace (EventLike): The new namespace to move the task to.

        Returns:
            Task: The moved instance of the `Task` class.
        """
        logger.debug(f"Moving task `{self.name}` to `{new_namespace}`")
        self._namespace.clear().concat(new_namespace)
        self.namespace = self._namespace.segments
        return self

    def nested_move_to(self, new_parent_namespace: EventLike) -> Self:
        """Move the task to a new namespace by nesting it under the new parent namespace.

        Args:
            new_parent_namespace (EventLike): The new parent namespace to move the task to.

        Returns:
            Task: The nested moved instance of the `Task` class.
        """
        logger.debug(f"Nested moving task `{self.name}` to `{new_parent_namespace}`")
        self._namespace.clear().concat(new_parent_namespace).concat(self.namespace)
        self.namespace = self._namespace.segments
        return self

    def update_task(self, goal: Optional[List[str] | str] = None, description: Optional[str] = None) -> Self:
        """Update the goal and description of the task.

        Args:
            goal (str|List[str], optional): The new goal of the task.
            description (str, optional): The new description of the task.

        Returns:
            Task: The updated instance of the `Task` class.
        """
        if goal:
            self.goals = goal if isinstance(goal, list) else [goal]
        if description:
            self.description = description
        return self

    async def get_output(self) -> T | None:
        """Get the output of the task.

        Returns:
            T: The output of the task.
        """
        logger.debug(f"Getting output for task {self.name}")
        return await self._output.get()

    def status_label(self, status: TaskStatus) -> str:
        """Return a formatted status label for the task.

        Args:
            status (fabricatio.constants.TaskStatus): The status of the task.

        Returns:
            str: The formatted status label.
        """
        return self._namespace.derive(self.name).push(status).collapse()

    @property
    def pending_label(self) -> str:
        """Return the pending status label for the task.

        Returns:
            str: The pending status label.
        """
        return self.status_label(TaskStatus.Pending)

    @property
    def running_label(self) -> str:
        """Return the running status label for the task.

        Returns:
            str: The running status label.
        """
        return self.status_label(TaskStatus.Running)

    @property
    def finished_label(self) -> str:
        """Return the finished status label for the task.

        Returns:
            str: The finished status label.
        """
        return self.status_label(TaskStatus.Finished)

    @property
    def failed_label(self) -> str:
        """Return the failed status label for the task.

        Returns:
            str: The failed status label.
        """
        return self.status_label(TaskStatus.Failed)

    @property
    def cancelled_label(self) -> str:
        """Return the cancelled status label for the task.

        Returns:
            str: The cancelled status label.
        """
        return self.status_label(TaskStatus.Cancelled)

    async def finish(self, output: T) -> Self:
        """Mark the task as finished and set the output.

        Args:
            output (T): The output of the task.

        Returns:
            Task: The finished instance of the `Task` class.
        """
        logger.info(f"Finishing task {self.name}")
        self._status = TaskStatus.Finished
        await self._output.put(output)
        logger.debug(f"Output set for task {self.name}")
        await ENV.emit_async(self.finished_label, self)
        logger.debug(f"Emitted finished event for task {self.name}")
        return self

    async def start(self) -> Self:
        """Mark the task as running.

        Returns:
            Task: The running instance of the `Task` class.
        """
        logger.info(f"Starting task `{self.name}`")
        self._status = TaskStatus.Running
        await ENV.emit_async(self.running_label, self)
        return self

    async def cancel(self) -> Self:
        """Mark the task as cancelled.

        Returns:
            Task: The cancelled instance of the `Task` class.
        """
        logger.info(f"Cancelling task `{self.name}`")
        self._status = TaskStatus.Cancelled
        await self._output.put(None)
        await ENV.emit_async(self.cancelled_label, self)
        return self

    async def fail(self) -> Self:
        """Mark the task as failed.

        Returns:
            Task: The failed instance of the `Task` class.
        """
        logger.info(f"Failing task `{self.name}`")
        self._status = TaskStatus.Failed
        await self._output.put(None)
        await ENV.emit_async(self.failed_label, self)
        return self

    def publish(self, new_namespace: Optional[EventLike] = None) -> Self:
        """Publish the task to the event bus.

        Args:
            new_namespace(EventLike, optional): The new namespace to move the task to.

        Returns:
            Task: The published instance of the `Task` class.
        """
        if new_namespace:
            self.move_to(new_namespace)
        logger.info(f"Publishing task `{(label := self.pending_label)}`")
        ENV.emit_future(label, self)
        return self

    async def delegate(self, new_namespace: Optional[EventLike] = None) -> T | None:
        """Delegate the task to the event.

        Args:
            new_namespace(EventLike, optional): The new namespace to move the task to.

        Returns:
            T|None: The output of the task.
        """
        if new_namespace:
            self.move_to(new_namespace)
        logger.info(f"Delegating task `{(label := self.pending_label)}`")
        ENV.emit_future(label, self)
        return await self.get_output()

    def delegate_blocking(self, new_namespace: Optional[EventLike] = None) -> T | None:
        """Delegate the task to the event in a blocking manner.

        Args:
            new_namespace (EventLike, optional): The new namespace to move the task to.

        Returns:
            T|None: The output of the task.
        """
        return run(self.delegate(new_namespace))

    @property
    def briefing(self) -> str:
        """Return a briefing of the task including its goal.

        Returns:
            str: The briefing of the task.
        """
        return TEMPLATE_MANAGER.render_template(
            CONFIG.templates.task_briefing_template,
            self.model_dump(),
        )

    def is_running(self) -> bool:
        """Check if the task is running.

        Returns:
            bool: True if the task is running, False otherwise.
        """
        return self._status == TaskStatus.Running

    def is_finished(self) -> bool:
        """Check if the task is finished.

        Returns:
            bool: True if the task is finished, False otherwise.
        """
        return self._status == TaskStatus.Finished

    def is_failed(self) -> bool:
        """Check if the task is failed.

        Returns:
            bool: True if the task is failed, False otherwise.
        """
        return self._status == TaskStatus.Failed

    def is_cancelled(self) -> bool:
        """Check if the task is cancelled.

        Returns:
            bool: True if the task is cancelled, False otherwise.
        """
        return self._status == TaskStatus.Cancelled

    def is_pending(self) -> bool:
        """Check if the task is pending.

        Returns:
            bool: True if the task is pending, False otherwise.
        """
        return self._status == TaskStatus.Pending
