from enum import Enum
from typing import Self

from pydantic import Field, PrivateAttr

from fabricatio.core import env
from fabricatio.models.generic import WithBriefing


class TaskStatus(Enum):
    Pending = "pending"
    Running = "running"
    Finished = "finished"
    Failed = "failed"
    Cancelled = "cancelled"


class Task[T](WithBriefing):
    _output: T = PrivateAttr(default="")
    status: TaskStatus = Field(default=TaskStatus.Pending)
    goal: str = Field(default="")

    def status_label(self, status: TaskStatus):
        return f"{self.name}-{status.value}"

    @property
    def pending_label(self):
        return self.status_label(TaskStatus.Pending)

    @property
    def running_label(self):
        return self.status_label(TaskStatus.Running)

    @property
    def finished_label(self):
        return self.status_label(TaskStatus.Finished)

    @property
    def failed_label(self):
        return self.status_label(TaskStatus.Failed)

    @property
    def cancelled_label(self):
        return self.status_label(TaskStatus.Cancelled)

    def finish(self, output: T) -> Self:
        self.status = TaskStatus.Finished
        self._output = output
        env.emit(self.failed_label, self)
        return self

    def start(self) -> Self:
        self.status = TaskStatus.Running
        env.emit(self.running_label, self)
        return self

    def cancel(self) -> Self:
        self.status = TaskStatus.Cancelled
        env.emit(self.cancelled_label, self)
        return self

    def fail(self) -> Self:
        self.status = TaskStatus.Failed
        env.emit(self.failed_label, self)
        return self

    @property
    def briefing(self) -> str:
        return f"{super().briefing}\n{self.goal}"
