"""This module defines the Task class, which represents a task with a status and output.

It includes methods to manage the task's lifecycle, such as starting, finishing, cancelling, and failing the task.
"""

from asyncio import Queue
from enum import Enum
from typing import Optional, Self

from pydantic import Field, PrivateAttr

from fabricatio.config import configs
from fabricatio.core import env
from fabricatio.journal import logger
from fabricatio.models.generic import WithBriefing, WithJsonExample


class TaskStatus(Enum):
    """Enum that represents the status of a task."""

    Pending = "pending"
    Running = "running"
    Finished = "finished"
    Failed = "failed"
    Cancelled = "cancelled"


class Task[T](WithBriefing, WithJsonExample):
    """Class that represents a task with a status and output.

    Attributes:
        name (str): The name of the task.
        description (str): The description of the task.
        _output (Queue): The output queue of the task.
        _status (TaskStatus): The status of the task.
        goal (str): The goal of the task.
    """

    name: str = Field(...)
    """The name of the task."""

    description: str = Field(default="")
    """The description of the task."""

    goal: str = Field(default="")
    """The goal of the task."""

    _output: Queue = PrivateAttr(default_factory=lambda: Queue(maxsize=1))
    """The output queue of the task."""
    _status: TaskStatus = PrivateAttr(default=TaskStatus.Pending)
    """The status of the task."""

    @classmethod
    def simple_task(cls, name: str, goal: str, description: str) -> Self:
        """Create a simple task with a name, goal, and description.

        Args:
            name (str): The name of the task.
            goal (str): The goal of the task.
            description (str): The description of the task.

        Returns:
            Self: A new instance of the Task class.
        """
        return cls(name=name, goal=goal, description=description)

    def update_task(self, goal: Optional[str] = None, description: Optional[str] = None) -> Self:
        """Update the goal and description of the task.

        Args:
            goal (Optional[str]): The new goal of the task.
            description (Optional[str]): The new description of the task.

        Returns:
            Self: The updated instance of the Task class.
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
        return f"{self.name}{configs.pymitter.delimiter}{status.value}"

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
            Self: The finished instance of the Task class.
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
            Self: The running instance of the Task class.
        """
        logger.info(f"Starting task {self.name}")
        self._status = TaskStatus.Running
        await env.emit_async(self.running_label, self)
        return self

    async def cancel(self) -> Self:
        """Mark the task as cancelled.

        Returns:
            Self: The cancelled instance of the Task class.
        """
        self._status = TaskStatus.Cancelled
        await env.emit_async(self.cancelled_label, self)
        return self

    async def fail(self) -> Self:
        """Mark the task as failed.

        Returns:
            Self: The failed instance of the Task class.
        """
        logger.error(f"Task {self.name} failed")
        self._status = TaskStatus.Failed
        await env.emit_async(self.failed_label, self)
        return self

    async def publish(self) -> Self:
        """Publish the task to the environment.

        Returns:
            Self: The published instance of the Task class.
        """
        logger.info(f"Publishing task {self.name}")
        await env.emit_async(self.pending_label, self)
        return self

    async def delegate(self) -> T:
        """Delegate the task to the environment.

        Returns:
            T: The output of the task.
        """
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
