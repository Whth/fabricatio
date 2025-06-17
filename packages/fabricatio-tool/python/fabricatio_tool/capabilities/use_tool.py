"""This module defines the UseToolBox class, which represents the usage of tools in a task.

It extends the UseLLM class and provides methods to manage and use toolboxes and tools within tasks.
"""

from abc import ABC
from typing import List, Optional, Set, Unpack

from fabricatio_core import Task, logger
from fabricatio_core.capabilities.usages import UseLLM
from fabricatio_core.models.kwargs_types import ChooseKwargs
from fabricatio_core.utils import ok, override_kwargs
from pydantic import Field

from fabricatio_tool.models.tool import Tool, ToolBox


class UseToolBox(UseLLM, ABC):
    """A class representing the usage of tools in a task.

    This class extends LLMUsage and provides methods to manage and use toolboxes and tools within tasks.
    """

    toolboxes: Set[ToolBox] = Field(default_factory=set)
    """A set of toolboxes used by the instance."""

    async def choose_toolboxes(
        self,
        task: Task,
        **kwargs: Unpack[ChooseKwargs[ToolBox]],
    ) -> Optional[List[ToolBox]]:
        """Asynchronously executes a multi-choice decision-making process to choose toolboxes.

        Args:
            task (Task): The task for which to choose toolboxes.
            **kwargs (Unpack[LLMKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            Optional[List[ToolBox]]: The selected toolboxes.
        """
        if not self.toolboxes:
            logger.warning("No toolboxes available.")
            return []
        return await self.achoose(
            instruction=task.briefing,
            choices=list(self.toolboxes),
            **kwargs,
        )

    async def choose_tools(
        self,
        task: Task,
        toolbox: ToolBox,
        **kwargs: Unpack[ChooseKwargs[Tool]],
    ) -> Optional[List[Tool]]:
        """Asynchronously executes a multi-choice decision-making process to choose tools.

        Args:
            task (Task): The task for which to choose tools.
            toolbox (ToolBox): The toolbox from which to choose tools.
            **kwargs (Unpack[LLMKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            Optional[List[Tool]]: The selected tools.
        """
        if not toolbox.tools:
            logger.warning(f"No tools available in toolbox {toolbox.name}.")
            return []
        return await self.achoose(
            instruction=task.briefing,
            choices=toolbox.tools,
            **kwargs,
        )

    async def gather_tools_fine_grind(
        self,
        task: Task,
        box_choose_kwargs: Optional[ChooseKwargs[ToolBox]] = None,
        tool_choose_kwargs: Optional[ChooseKwargs[Tool]] = None,
    ) -> List[Tool]:
        """Asynchronously gathers tools based on the provided task and toolbox and tool selection criteria.

        Args:
            task (Task): The task for which to gather tools.
            box_choose_kwargs (Optional[ChooseKwargs]): Keyword arguments for choosing toolboxes.
            tool_choose_kwargs (Optional[ChooseKwargs]): Keyword arguments for choosing tools.

        Returns:
            List[Tool]: A list of tools gathered based on the provided task and toolbox and tool selection criteria.
        """
        box_choose_kwargs = box_choose_kwargs or {}
        tool_choose_kwargs = tool_choose_kwargs or {}

        # Choose the toolboxes
        chosen_toolboxes = ok(await self.choose_toolboxes(task, **box_choose_kwargs))
        # Choose the tools
        chosen_tools = []
        for toolbox in chosen_toolboxes:
            chosen_tools.extend(ok(await self.choose_tools(task, toolbox, **tool_choose_kwargs)))
        return chosen_tools

    async def gather_tools(self, task: Task, **kwargs: Unpack[ChooseKwargs[Tool]]) -> List[Tool]:
        """Asynchronously gathers tools based on the provided task.

        Args:
            task (Task): The task for which to gather tools.
            **kwargs (Unpack[ChooseKwargs]): Keyword arguments for choosing tools.

        Returns:
            List[Tool]: A list of tools gathered based on the provided task.
        """
        return await self.gather_tools_fine_grind(task, ChooseKwargs(**override_kwargs(kwargs, default=None)), kwargs)
