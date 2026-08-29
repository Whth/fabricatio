"""This module contains the HandleTask class, which is responsible for handling tasks based on task objects.

It utilizes tool usage code drafting and execution mechanisms to perform tasks asynchronously.
The class interacts with tools and manages their execution workflow.
"""

from abc import ABC
from typing import Any, Unpack

from fabricatio_context.models.context import ContextLog
from fabricatio_core.journal import logger
from fabricatio_core.models.kwargs_types import ChooseKwargs, ValidateKwargs
from fabricatio_core.rust import TASK, TEMPLATE_MANAGER
from fabricatio_core.utils import no_default

from fabricatio_tool.capabilities.use_tool import UseTool
from fabricatio_tool.config import tool_config
from fabricatio_tool.models.collector import ApplicationError, ResultCollector
from fabricatio_tool.models.executor import ToolExecutor
from fabricatio_tool.models.feedback import failure_entries, feedback_log, summarize_collector
from fabricatio_tool.models.tool import Tool, ToolBox


class Handle(UseTool, ABC):
    """A class that handles a task based on a task object."""

    async def draft_tool_usage_code(
        self,
        request: str,
        tools: list[Tool],
        data: dict[str, Any],
        output_spec: dict[str, str] | None = None,
        exec_feedback: str | None = None,
        send_to: str | None = TASK,
        **kwargs: Unpack[ValidateKwargs[str]],
    ) -> str | None:
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
                "exec_feedback": exec_feedback,
            },
        )
        logger.debug(f"Code Drafting Question: \n{q}")

        return await self.acode_string(q, "python", send_to=send_to, **kwargs)

    async def handle_fine_grind(
        self,
        request: str,
        data: dict[str, Any],
        output_spec: dict[str, str] | None = None,
        box_choose_kwargs: ChooseKwargs[ToolBox] | None = None,
        tool_choose_kwargs: ChooseKwargs[Tool] | None = None,
        max_feedback_rounds: int | None = None,
        send_to: str | None = TASK,
        **kwargs: Unpack[ValidateKwargs[str]],
    ) -> ResultCollector | None:
        """Asynchronously handle a task, re-drafting from execution feedback on failure.

        Args:
            request: The task request to satisfy.
            data: Input data available to the generated code.
            output_spec: Optional mapping of result keys to their descriptions.
            box_choose_kwargs: Kwargs for toolbox selection.
            tool_choose_kwargs: Kwargs for tool selection.
            max_feedback_rounds: Extra re-drafting rounds on execution failure; overrides
                ``tool_config.max_feedback_rounds`` when not None. 0 disables the loop.
            send_to: Routing-group variant for the LLM call. Resolved against
                the agent variant registry (see ``fabricatio_core.rust``). Defaults to
                ``TASK``.
            **kwargs: Additional unpacked keyword arguments for the LLM call.

        Returns:
            An optional ResultCollector instance: the successful results when a round
            succeeded, or the last execution state otherwise.
        """
        logger.info(f"Handling task: \n{request}")

        rounds = tool_config.max_feedback_rounds if max_feedback_rounds is None else max(0, max_feedback_rounds)

        tools = await self.gather_tools_fine_grind(request, box_choose_kwargs, tool_choose_kwargs, send_to=send_to)
        logger.info(f"Gathered {[t.name for t in tools]}")

        if not tools:
            return None

        executor = ToolExecutor(candidates=tools, data=data)
        history: ContextLog = ContextLog()
        feedback: str | None = None
        for attempt in range(rounds + 1):
            source = await self.draft_tool_usage_code(
                request,
                tools,
                data,
                output_spec,
                exec_feedback=feedback,
                send_to=send_to,
                **kwargs,
            )
            if not source:
                return None
            try:
                await executor.execute(source)
            except ValueError as e:  # code-check rejections raise instead of surfacing via the collector
                executor.collector.submit(
                    tool_config.error_key,
                    ApplicationError(
                        exc_type=type(e).__name__,
                        message=str(e),
                        traceback="",
                        source=source,
                    ),
                )
            if executor.collector.error() is None:
                return executor.collector
            if attempt >= rounds:
                break
            payload = summarize_collector(executor.collector)
            history = history.with_entries(failure_entries(payload))
            feedback = feedback_log(payload, history=history).render()
            executor.collector.revoke(tool_config.error_key)
        return executor.collector

    async def handle(
        self,
        request: str,
        data: dict[str, Any] | None = None,
        output_spec: dict[str, str] | None = None,
        send_to: str | None = TASK,
        **kwargs: Unpack[ValidateKwargs[str]],
    ) -> ResultCollector | None:
        """Asynchronously handles a task based on a given task object and parameters."""
        okwargs = ChooseKwargs(**no_default(kwargs))

        return await self.handle_fine_grind(
            request,
            data or {},
            output_spec,
            box_choose_kwargs=okwargs,
            tool_choose_kwargs=okwargs,
            send_to=send_to,
            **kwargs,
        )
