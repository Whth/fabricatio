"""Module for the TaskList class, which represents a sequence of tasks designed to achieve an ultimate target.

This module contains the definition of the TaskList class, which is used to model a series
of tasks aimed at achieving a specific ultimate target. It inherits from the ProposedAble
interface and provides implementations for task sequence generation.
"""

from asyncio import gather
from typing import Any, Callable, List, Optional

from fabricatio_core import Task
from fabricatio_core.models.generic import ProposedAble
from fabricatio_core.rust import TEMPLATE_MANAGER
from pydantic import PrivateAttr

from fabricatio_digest.config import digest_config


class TaskList(ProposedAble):
    """A list of tasks designed to achieve an ultimate target."""

    ultimate_target: str
    """The ultimate target of the task list"""
    tasks: List[Task]
    """The tasks sequence that aims to achieve the ultimate target."""
    parallel: bool = False
    """Whether the tasks should be executed in parallel."""

    _before_exec_hooks: List[Callable[[], Any]] = PrivateAttr(default_factory=list)
    """A list of callables to be executed before each task in the task list"""

    _after_exec_hooks: List[Callable[[], Any]] = PrivateAttr(default_factory=list)
    """A list of callables to be executed after each task in the task list"""

    def _run_before_exec_hooks(self) -> None:
        for hook in self._before_exec_hooks:
            hook()

    def _run_after_exec_hooks(self) -> None:
        for hook in self._after_exec_hooks:
            hook()

    def add_before_exec_hook(self, hook: Callable[[], Any]) -> None:
        """Adds a hook to be executed before each task in the task list.

        Args:
            hook (Callable[[],Any]): The hook to be added.
        """
        self._before_exec_hooks.append(hook)

    def add_after_exec_hook(self, hook: Callable[[], Any]) -> None:
        """Adds a hook to be executed after each task in the task list.

        Args:
            hook (Callable[[],Any]): The hook to be added.
        """
        self._after_exec_hooks.append(hook)

    def clear_before_exec_hooks(self) -> None:
        """Clears all before execution hooks."""
        self._before_exec_hooks.clear()

    def clear_after_exec_hooks(self) -> None:
        """Clears all after execution hooks."""
        self._after_exec_hooks.clear()

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
            self._run_before_exec_hooks()
            res = await gather(*[task.delegate() for task in self.tasks])
            self._run_after_exec_hooks()
            return res
        res = []
        for task in self.tasks:

            async def _task_wrapper[T](cur_task: Task[T] = task) -> T | None:
                """Wrapper function for task execution."""
                self._run_before_exec_hooks()
                result = await cur_task.delegate()
                self._run_after_exec_hooks()
                return result

            res.append(await _task_wrapper())

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
