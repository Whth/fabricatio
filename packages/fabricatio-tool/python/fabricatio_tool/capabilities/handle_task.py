"""This module contains the HandleTask class, which is responsible for handling tasks based on task objects.

It utilizes tool usage code drafting and execution mechanisms to perform tasks asynchronously.
The class interacts with tools and manages their execution workflow.
"""

from abc import ABC
from typing import Any, Dict, List, Optional, Unpack

from fabricatio_capabilities.config import capabilities_config
from fabricatio_core import Task
from fabricatio_core.journal import logger
from fabricatio_core.models.kwargs_types import ChooseKwargs, ValidateKwargs
from fabricatio_core.rust import TEMPLATE_MANAGER
from fabricatio_core.utils import override_kwargs

from fabricatio_tool.capabilities.use_tool import UseToolBox
from fabricatio_tool.models.tool import ResultCollector, Tool, ToolExecutor


class HandleTask(UseToolBox, ABC):
    """A class that handles a task based on a task object."""

    async def draft_tool_usage_code(
        self,
        task: Task,
        tools: List[Tool],
        data: Dict[str, Any],
        **kwargs: Unpack[ValidateKwargs[str]],
    ) -> Optional[str]:
        """Asynchronously drafts the tool usage code for a task based on a given task object and tools."""
        logger.info(f"Drafting tool usage code for task: {task.briefing}")

        if not tools:
            err = "Tools must be provided to draft the tool usage code."
            logger.error(err)
            raise ValueError(err)

        q = TEMPLATE_MANAGER.render_template(
            capabilities_config.draft_tool_usage_code_template,
            {
                "collector_help": ResultCollector.__doc__,
                "collector_varname": ToolExecutor.collector_varname,
                "fn_header": ToolExecutor(candidates=tools, data=data).signature(),
                "task": task.briefing,
                "deps": task.dependencies_prompt,
                "tools": [{"name": t.name, "briefing": t.briefing} for t in tools],
                "data": data,
            },
        )
        logger.debug(f"Code Drafting Question: \n{q}")

        return await self.acode_string(q, "python", **kwargs)

    async def handle_fine_grind(
        self,
        task: Task,
        data: Dict[str, Any],
        box_choose_kwargs: Optional[ChooseKwargs] = None,
        tool_choose_kwargs: Optional[ChooseKwargs] = None,
        **kwargs: Unpack[ValidateKwargs[str]],
    ) -> Optional[ResultCollector]:
        """Asynchronously handles a task based on a given task object and parameters."""
        logger.info(f"Handling task: \n{task.briefing}")

        tools = await self.gather_tools_fine_grind(task, box_choose_kwargs, tool_choose_kwargs)
        logger.info(f"Gathered {[t.name for t in tools]}")

        if tools and (source := await self.draft_tool_usage_code(task, tools, data, **kwargs)):
            return await ToolExecutor(candidates=tools, data=data).execute(source)

        return None

    async def handle(
        self, task: Task, data: Dict[str, Any], **kwargs: Unpack[ValidateKwargs[str]]
    ) -> Optional[ResultCollector]:
        """Asynchronously handles a task based on a given task object and parameters."""
        okwargs = ChooseKwargs(**override_kwargs(kwargs, default=None))

        return await self.handle_fine_grind(task, data, box_choose_kwargs=okwargs, tool_choose_kwargs=okwargs, **kwargs)
