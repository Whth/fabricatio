from asyncio import Queue
from enum import Enum
from typing import Self

from pydantic import Field, PrivateAttr

from fabricatio.config import configs
from fabricatio.core import env
from fabricatio.logging import logger
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

    _output: Queue = PrivateAttr(default_factory=lambda: Queue(maxsize=1))
    status: TaskStatus = Field(default=TaskStatus.Pending)
    """The status of the task."""
    goal: str = Field(default="")
    """The goal of the task."""

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

    def finish(self, output: T) -> Self:
        """Mark the task as finished and set the output."""
        logger.info(f"Finishing task {self.name}")
        self.status = TaskStatus.Finished
        self._output.put(output)
        env.emit(self.failed_label, self)
        return self

    def start(self) -> Self:
        """Mark the task as running."""
        logger.info(f"Starting task {self.name}")
        self.status = TaskStatus.Running
        env.emit(self.running_label, self)
        return self

    def cancel(self) -> Self:
        """Mark the task as cancelled."""
        self.status = TaskStatus.Cancelled
        env.emit(self.cancelled_label, self)
        return self

    def fail(self) -> Self:
        """Mark the task as failed."""
        logger.error(f"Task {self.name} failed")
        self.status = TaskStatus.Failed
        env.emit(self.failed_label, self)
        return self

    @property
    def briefing(self) -> str:
        """Return a briefing of the task including its goal."""
        return f"{super().briefing}\n{self.goal}"
