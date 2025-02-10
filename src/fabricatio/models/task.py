"""This module defines the `Task` class, which represents a task with a status and output.

It includes methods to manage the task's lifecycle, such as starting, finishing, cancelling, and failing the task.
"""

from asyncio import Queue
from enum import Enum
from typing import Any, List, Optional, Self

from pydantic import Field, PrivateAttr

from fabricatio.core import env
from fabricatio.journal import logger
from fabricatio.models.events import Event
from fabricatio.models.generic import WithBriefing, WithJsonExample


class TaskStatus(Enum):
    """An enumeration representing the status of a task.

    Attributes:
        Pending: The task is pending.
        Running: The task is currently running.
        Finished: The task has been successfully completed.
        Failed: The task has failed.
        Cancelled: The task has been cancelled.
    """

    Pending = "pending"
    Running = "running"
    Finished = "finished"
    Failed = "failed"
    Cancelled = "cancelled"


class Task[T](WithBriefing, WithJsonExample):
    """A class representing a task with a status and output.

    Attributes:
        name (str): The name of the task.
        description (str): The description of the task.
        goal (str): The goal of the task.
    """

    name: str = Field(...)
    """The name of the task."""

    description: str = Field(default="")
    """The description of the task."""

    goal: str = Field(default="")
    """The goal of the task."""

    dependencies: List[str] = Field(default_factory=list)
    """The file dependencies of the task, a list of file paths."""

    namespace: List[str] = Field(default_factory=list)
    """The namespace of the task, a list of namespace segment, as string."""

    _output: Queue = PrivateAttr(default_factory=lambda: Queue(maxsize=1))
    """The output queue of the task."""

    _status: TaskStatus = PrivateAttr(default=TaskStatus.Pending)
    """The status of the task."""

    _namespace: Event = PrivateAttr(default_factory=Event)
    """The namespace of the task as an event, which is generated from the namespace list."""

    def model_post_init(self, __context: Any) -> None:
        """Initialize the task with a namespace event."""
        self._namespace.segments.extend(self.namespace)

    @classmethod
    def simple_task(cls, name: str, goal: str, description: str) -> Self:
        """Create a simple task with a name, goal, and description.

        Args:
            name (str): The name of the task.
            goal (str): The goal of the task.
            description (str): The description of the task.

        Returns:
            Task: A new instance of the `Task` class.
        """
        return cls(name=name, goal=goal, description=description)

    def update_task(self, goal: Optional[str] = None, description: Optional[str] = None) -> Self:
        """Update the goal and description of the task.

        Args:
            goal (str, optional): The new goal of the task.
            description (str, optional): The new description of the task.

        Returns:
            Task: The updated instance of the `Task` class.
        """
        if goal:
            self.goal = goal
        if description:
            self.description = description
        return self

    async def get_output(self) -> T:
        """Get the output of the task.

        Returns:
            T: The output of the task.
        """
        logger.debug(f"Getting output for task {self.name}")
        return await self._output.get()

    def status_label(self, status: TaskStatus) -> str:
        """Return a formatted status label for the task.

        Args:
            status (TaskStatus): The status of the task.

        Returns:
            str: The formatted status label.
        """
        return self._namespace.derive(self.name).push(status.value).collapse()

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
        await env.emit_async(self.finished_label, self)
        logger.debug(f"Emitted finished event for task {self.name}")
        return self

    async def start(self) -> Self:
        """Mark the task as running.

        Returns:
            Task: The running instance of the `Task` class.
        """
        logger.info(f"Starting task {self.name}")
        self._status = TaskStatus.Running
        await env.emit_async(self.running_label, self)
        return self

    async def cancel(self) -> Self:
        """Mark the task as cancelled.

        Returns:
            Task: The cancelled instance of the `Task` class.
        """
        self._status = TaskStatus.Cancelled
        await env.emit_async(self.cancelled_label, self)
        return self

    async def fail(self) -> Self:
        """Mark the task as failed.

        Returns:
            Task: The failed instance of the `Task` class.
        """
        logger.error(f"Task {self.name} failed")
        self._status = TaskStatus.Failed
        await env.emit_async(self.failed_label, self)
        return self

    async def publish(self) -> Self:
        """Publish the task to the event bus."""
        logger.info(f"Publishing task {self.name}")
        await env.emit_async(self.pending_label, self)
        return self

    async def delegate(self) -> T:
        """Delegate the task to the event bus and wait for the output."""
        logger.info(f"Delegating task {self.name}")
        await env.emit_async(self.pending_label, self)
        return await self.get_output()

    @property
    def briefing(self) -> str:
        """Return a briefing of the task including its goal.

        Returns:
            str: The briefing of the task.
        """
        return f"{super().briefing}\n{self.goal}"
