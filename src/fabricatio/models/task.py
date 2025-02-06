from enum import Enum
from typing import Self

from pydantic import Field, PrivateAttr

from fabricatio.core import env
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

    _output: T = PrivateAttr(default="")
    status: TaskStatus = Field(default=TaskStatus.Pending)
    """The status of the task."""
    goal: str = Field(default="")
    """The goal of the task."""

    def status_label(self, status: TaskStatus):
        """Return a formatted status label for the task."""
        return f"{self.name}-{status.value}"

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
        self.status = TaskStatus.Finished
        self._output = output
        env.emit(self.failed_label, self)
        return self

    def start(self) -> Self:
        """Mark the task as running."""
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
        self.status = TaskStatus.Failed
        env.emit(self.failed_label, self)
        return self

    @property
    def briefing(self) -> str:
        """Return a briefing of the task including its goal."""
        return f"{super().briefing}\n{self.goal}"
