from asyncio import Queue
from enum import Enum
from typing import Self

from pydantic import Field, PrivateAttr

from fabricatio.config import configs
from fabricatio.core import env
from fabricatio.journal import logger
from fabricatio.models.generic import WithBriefing


class TaskStatus(Enum):
    """Enum that represents the status of a task."""

    Pending = "pending"
    Running = "running"
    Finished = "finished"
    Failed = "failed"
    Cancelled = "cancelled"


class Task[T](WithBriefing):
    """Class that represents a task with a status and output."""

    name: str = Field(...)
    """The name of the task."""
    description: str = Field(default="")
    """The description of the task."""
    _output: Queue = PrivateAttr(default_factory=lambda: Queue(maxsize=1))
    status: TaskStatus = Field(default=TaskStatus.Pending)
    """The status of the task."""
    goal: str = Field(default="")
    """The goal of the task."""

    @classmethod
    def simple_task(cls, name: str, goal: str, description: str) -> Self:
        """Create a simple task with a name, goal, and description."""
        return cls(name=name, goal=goal, description=description)

    def update_task(self, goal: str = None, description: str = None) -> Self:
        """Update the goal and description of the task."""
        if goal:
            self.goal = goal
        if description:
            self.description = description
        return self

    async def get_output(self) -> T:
        """Get the output of the task."""
        logger.debug(f"Getting output for task {self.name}")
        return await self._output.get()

    def status_label(self, status: TaskStatus):
        """Return a formatted status label for the task."""
        return f"{self.name}{configs.pymitter.delimiter}{status.value}"

    @property
    def pending_label(self):
        """Return the pending status label for the task."""
        return self.status_label(TaskStatus.Pending)

    @property
    def running_label(self):
        """Return the running status label for the task."""
        return self.status_label(TaskStatus.Running)

    @property
    def finished_label(self):
        """Return the finished status label for the task."""
        return self.status_label(TaskStatus.Finished)

    @property
    def failed_label(self):
        """Return the failed status label for the task."""
        return self.status_label(TaskStatus.Failed)

    @property
    def cancelled_label(self):
        """Return the cancelled status label for the task."""
        return self.status_label(TaskStatus.Cancelled)

    async def finish(self, output: T) -> Self:
        """Mark the task as finished and set the output."""
        logger.info(f"Finishing task {self.name}")
        self.status = TaskStatus.Finished
        await self._output.put(output)
        logger.debug(f"Output set for task {self.name}")
        await env.emit_async(self.finished_label, self)
        logger.debug(f"Emitted finished event for task {self.name}")
        return self

    async def start(self) -> Self:
        """Mark the task as running."""
        logger.info(f"Starting task {self.name}")
        self.status = TaskStatus.Running
        await env.emit_async(self.running_label, self)
        return self

    async def cancel(self) -> Self:
        """Mark the task as cancelled."""
        self.status = TaskStatus.Cancelled
        await env.emit_async(self.cancelled_label, self)
        return self

    async def fail(self) -> Self:
        """Mark the task as failed."""
        logger.error(f"Task {self.name} failed")
        self.status = TaskStatus.Failed
        await env.emit_async(self.failed_label, self)
        return self

    async def publish(self) -> Self:
        """Publish the task to the environment."""
        logger.info(f"Publishing task {self.name}")
        await env.emit_async(self.pending_label, self)
        return self

    async def delegate(self) -> T:
        """Delegate the task to the environment."""
        logger.info(f"Delegating task {self.name}")
        await env.emit_async(self.pending_label, self)
        return await self.get_output()

    @property
    def briefing(self) -> str:
        """Return a briefing of the task including its goal."""
        return f"{super().briefing}\n{self.goal}"
