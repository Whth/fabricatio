"""This module contains the HandleTask class, which serves as an abstract base class for handling tasks based on task objects.

It provides a structured mechanism for asynchronous task execution by leveraging code drafting and execution workflows.
The class facilitates interaction with various tools, managing their execution lifecycle and workflow.
"""

from abc import ABC
from typing import Any, Dict, Optional, Unpack

from fabricatio_core import Task
from fabricatio_core.models.kwargs_types import ChooseKwargs, ValidateKwargs
from fabricatio_core.utils import override_kwargs

from fabricatio_tool.capabilities.handle import Handle
from fabricatio_tool.models.collector import ResultCollector


class HandleTask(Handle, ABC):
    """A class that handles a task based on a task object, providing extended functionality for processing and execution.

    This class extends Handle and implements task-specific operations to support complex workflows,
    including parameter management, tool integration, and result collection.
    """

    async def handle_task(
        self, task: Task, data: Dict[str, Any], **kwargs: Unpack[ValidateKwargs[str]]
    ) -> Optional[ResultCollector]:
        """Asynchronously handles a task based on a given task object and parameters with enhanced control features.

        This method prepares execution parameters and delegates task processing to the fine-grained execution handler.
        It supports customizable behavior through keyword arguments for both box and tool selection processes.

        Args:
            task: The task object containing instructions and metadata for execution.
            data: A dictionary containing input data for the task.
            **kwargs: Additional unpacked keyword arguments for customization of execution behavior.

        Returns:
            An optional ResultCollector instance containing the results of task execution.
        """
        okwargs = ChooseKwargs(**override_kwargs(kwargs, default=None))
        return await self.handle_fine_grind(
            f"{task.dependencies_prompt}\n\n\n{task.briefing}",
            data,
            box_choose_kwargs=okwargs,
            tool_choose_kwargs=okwargs,
            **kwargs,
        )
