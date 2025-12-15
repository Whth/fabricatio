"""This module contains the HandleTask class, which is responsible for handling tasks based on task objects.

It utilizes tool usage code drafting and execution mechanisms to perform tasks asynchronously.
The class interacts with tools and manages their execution workflow.
"""

from abc import ABC
from typing import Any, Dict, List, Optional, Unpack

from fabricatio_core.journal import logger
from fabricatio_core.models.kwargs_types import ChooseKwargs, ValidateKwargs
from fabricatio_core.rust import TEMPLATE_MANAGER
from fabricatio_core.utils import override_kwargs

from fabricatio_tool.capabilities.use_tool import UseTool
from fabricatio_tool.config import tool_config
from fabricatio_tool.models.collector import ResultCollector
from fabricatio_tool.models.executor import ToolExecutor
from fabricatio_tool.models.tool import Tool, ToolBox


class Handle(UseTool, ABC):
    """A class that handles a task based on a task object."""

    async def draft_tool_usage_code(
        self,
        request: str,
        tools: List[Tool],
        data: Dict[str, Any],
        output_spec: Optional[Dict[str, str]] = None,
        **kwargs: Unpack[ValidateKwargs[str]],
    ) -> Optional[str]:
        """Asynchronously drafts the tool usage code for a task based on a given task object and tools."""
        logger.info(f"Drafting tool usage code for task: \n{request}")

        if not tools:
            err = "Tools must be provided to draft the tool usage code."
            logger.error(err)
            raise ValueError(err)

        q = TEMPLATE_MANAGER.render_template(
            tool_config.draft_tool_usage_code_template,
            {
                "collector_help": ResultCollector.__doc__,
                "collector_varname": ToolExecutor.collector_varname,
                "fn_header": ToolExecutor(candidates=tools, data=data).signature(),
                "request": request,
                "tools": [{"name": t.name, "briefing": t.briefing} for t in tools],
                "data": data,
                "output_spec": output_spec or {},
            },
        )
        logger.debug(f"Code Drafting Question: \n{q}")

        return await self.acode_string(q, "python", **kwargs)

    async def handle_fine_grind(
        self,
        request: str,
        data: Dict[str, Any],
        output_spec: Optional[Dict[str, str]] = None,
        box_choose_kwargs: Optional[ChooseKwargs[ToolBox]] = None,
        tool_choose_kwargs: Optional[ChooseKwargs[Tool]] = None,
        **kwargs: Unpack[ValidateKwargs[str]],
    ) -> Optional[ResultCollector]:
        """Asynchronously handles a task based on a given task object and parameters."""
        logger.info(f"Handling task: \n{request}")

        tools = await self.gather_tools_fine_grind(request, box_choose_kwargs, tool_choose_kwargs)
        logger.info(f"Gathered {[t.name for t in tools]}")

        if tools and (source := await self.draft_tool_usage_code(request, tools, data, output_spec, **kwargs)):
            return await ToolExecutor(candidates=tools, data=data).execute(source)

        return None

    async def handle(
        self,
        request: str,
        data: Optional[Dict[str, Any]] = None,
        output_spec: Optional[Dict[str, str]] = None,
        **kwargs: Unpack[ValidateKwargs[str]],
    ) -> Optional[ResultCollector]:
        """Asynchronously handles a task based on a given task object and parameters."""
        okwargs = ChooseKwargs(**override_kwargs(kwargs, default=None))

        return await self.handle_fine_grind(
            request,
            data or {},
            output_spec,
            box_choose_kwargs=okwargs,
            tool_choose_kwargs=okwargs,
            **kwargs,
        )
