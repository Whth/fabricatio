"""A module containing constants used throughout the library."""
from enum import StrEnum


class TaskStatus(StrEnum):
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
