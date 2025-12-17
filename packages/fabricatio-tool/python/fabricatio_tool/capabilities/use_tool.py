"""This module defines the UseToolBox class, which represents the usage of tools in a task.

It extends the UseLLM class and provides methods to manage and use toolboxes and tools within tasks.
"""

from abc import ABC
from typing import List, Optional, Set, Unpack

from fabricatio_core import logger
from fabricatio_core.capabilities.usages import UseLLM
from fabricatio_core.models.generic import ScopedConfig
from fabricatio_core.models.kwargs_types import ChooseKwargs
from fabricatio_core.utils import ok, override_kwargs
from pydantic import Field

from fabricatio_tool.models.tool import Tool, ToolBox


class ToolConfig(ScopedConfig):
    """A configuration class for tool usage."""

    toolboxes: Set[ToolBox] = Field(default_factory=set)
    """A set of toolboxes used by the instance."""


class UseTool(UseLLM, ToolConfig, ABC):
    """A class representing the usage of tools in a task.

    This class extends LLMUsage and provides methods to manage and use toolboxes and tools within tasks.
    """

    async def choose_toolboxes(
        self,
        request: str,
        **kwargs: Unpack[ChooseKwargs[ToolBox]],
    ) -> Optional[List[ToolBox]]:
        """Asynchronously executes a multi-choice decision-making process to choose toolboxes.

        Args:
            request (str): The request for toolbox selection.
            **kwargs (Unpack[LLMKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            Optional[List[ToolBox]]: The selected toolboxes.
        """
        if not self.toolboxes:
            logger.warn("No toolboxes available.")
            return []

        def _is_included_fn(query: Set[str], toolbox: ToolBox) -> bool:
            return toolbox.name in query or any(t.name in query for t in toolbox.tools)

        return await self.achoose(
            instruction=request,
            choices=list(self.toolboxes),
            is_included_fn=_is_included_fn,
            **kwargs,
        )

    async def choose_tools(
        self,
        request: str,
        toolbox: ToolBox,
        **kwargs: Unpack[ChooseKwargs[Tool]],
    ) -> Optional[List[Tool]]:
        """Asynchronously executes a multi-choice decision-making process to choose tools.

        Args:
            request (str): The request for tool selection.
            toolbox (ToolBox): The toolbox from which to choose tools.
            **kwargs (Unpack[LLMKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            Optional[List[Tool]]: The selected tools.
        """
        if not toolbox.tools:
            logger.warn(f"No tools available in toolbox {toolbox.name}.")
            return []
        return await self.achoose(
            instruction=request,
            choices=toolbox.tools,
            **kwargs,
        )

    async def gather_tools_fine_grind(
        self,
        request: str,
        box_choose_kwargs: Optional[ChooseKwargs[ToolBox]] = None,
        tool_choose_kwargs: Optional[ChooseKwargs[Tool]] = None,
    ) -> List[Tool]:
        """Asynchronously gathers tools based on the provided request and toolbox and tool selection criteria.

        Args:
            request (str): The request for gathering tools.
            box_choose_kwargs (Optional[ChooseKwargs]): Keyword arguments for choosing toolboxes.
            tool_choose_kwargs (Optional[ChooseKwargs]): Keyword arguments for choosing tools.

        Returns:
            List[Tool]: A list of tools gathered based on the provided request and selection criteria.
        """
        box_choose_kwargs = box_choose_kwargs or {}
        tool_choose_kwargs = tool_choose_kwargs or {}

        # Choose the toolboxes
        chosen_toolboxes = ok(await self.choose_toolboxes(request, **box_choose_kwargs))
        # Choose the tools
        chosen_tools = []
        for toolbox in chosen_toolboxes:
            chosen_tools.extend(ok(await self.choose_tools(request, toolbox, **tool_choose_kwargs)))
        return chosen_tools

    async def gather_tools(self, request: str, **kwargs: Unpack[ChooseKwargs[Tool]]) -> List[Tool]:
        """Asynchronously gathers tools based on the provided request.

        Args:
            request (str): The request for gathering tools.
            **kwargs (Unpack[ChooseKwargs]): Keyword arguments for choosing tools.

        Returns:
            List[Tool]: A list of tools gathered based on the provided request.
        """
        return await self.gather_tools_fine_grind(
            request, ChooseKwargs(**override_kwargs(kwargs, default=None)), kwargs
        )
