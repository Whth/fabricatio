"""Module for the TaskList class, which represents a sequence of tasks designed to achieve an ultimate target.

This module contains the definition of the TaskList class, which is used to model a series
of tasks aimed at achieving a specific ultimate target. It inherits from the ProposedAble
interface and provides implementations for task sequence generation.
"""

from asyncio import gather
from typing import Any, List

from fabricatio_core import Task
from fabricatio_core.models.generic import ProposedAble


class TaskList(ProposedAble):
    """A list of tasks designed to achieve an ultimate target."""

    ultimate_target: str
    """The ultimate target of the task list"""

    tasks: List[Task]
    """The tasks sequence that aims to achieve the ultimate target."""

    async def sequential(self) -> List[Any]:
        """Generate tasks sequentially."""
        res = []
        for task in self.tasks:
            res.append(await task.delegate())

        return res

    async def parallel(self) -> List[Any]:
        """Generate tasks in parallel."""
        return await gather(*[task.delegate() for task in self.tasks])
