"""Module for the TaskList class, which represents a sequence of tasks designed to achieve an ultimate target.

This module contains the definition of the TaskList class, which is used to model a series
of tasks aimed at achieving a specific ultimate target. It inherits from the ProposedAble
interface and provides implementations for task sequence generation.
"""

from asyncio import gather
from typing import Any, List, Optional

from fabricatio_core import Task
from fabricatio_core.models.generic import ProposedAble
from fabricatio_core.rust import TEMPLATE_MANAGER

from fabricatio_digest.config import digest_config


class TaskList(ProposedAble):
    """A list of tasks designed to achieve an ultimate target."""

    ultimate_target: str
    """The ultimate target of the task list"""
    tasks: List[Task]
    """The tasks sequence that aims to achieve the ultimate target."""
    parallel: bool = False
    """Whether the tasks should be executed in parallel."""

    async def execute(self, parallel: Optional[bool] = None) -> List[Any]:
        """Asynchronously executes the sequence of tasks in the task list.

        If the parallel flag is set to True, all tasks are executed concurrently.
        Otherwise, tasks are executed sequentially. This method provides an awaitable
        interface for executing all tasks either in parallel using asyncio.gather or
        sequentially in a loop.

        Args:
            parallel (Optional[bool]): Flag indicating whether tasks should be executed
                in parallel. If None, defaults to the instance's parallel attribute.

        Returns:
            List[Any]: A list containing the results of each task execution, preserving
                the order of tasks as stored in the instance.
        """
        if parallel if parallel is not None else self.parallel:
            return await gather(*[task.delegate() for task in self.tasks])

        res = []
        for task in self.tasks:
            res.append(await task.delegate())

        return res

    def explain(self) -> str:
        """Generates an explanation for the task list.

        This method uses the task list template to generate an explanation for the task list.
        The template is loaded from the template manager and the task list is rendered using
        the task list template.

        Returns:
            str: An explanation for the task list.
        """
        return TEMPLATE_MANAGER.render_template(digest_config.task_list_explain_template, self.model_dump())
