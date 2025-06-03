"""A module for the task capabilities of the Fabricatio library."""

from abc import ABC
from types import CodeType
from typing import Any, Dict, List, Mapping, Optional, Tuple, Unpack

import ujson
from fabricatio_core import Task
from fabricatio_core.journal import logger
from fabricatio_core.models.generic import WithBriefing
from fabricatio_core.models.kwargs_types import ChooseKwargs, ValidateKwargs
from fabricatio_core.models.tool import Tool, ToolExecutor
from fabricatio_core.models.usages import LLMUsage, ToolBoxUsage
from fabricatio_core.parser import JsonCapture, PythonCapture
from fabricatio_core.rust import CONFIG, TEMPLATE_MANAGER

from fabricatio_capabilities.capabilities.propose import Propose
from fabricatio_capabilities.config import capabilities_config


class ProposeTask(Propose, ABC):
    """A class that proposes a task based on a prompt."""

    async def propose_task[T](
        self,
        prompt: str,
        **kwargs: Unpack[ValidateKwargs[Task[T]]],
    ) -> Optional[Task[T]]:
        """Asynchronously proposes a task based on a given prompt and parameters.

        Parameters:
            prompt: The prompt text for proposing a task, which is a string that must be provided.
            **kwargs: The keyword arguments for the LLM (Large Language Model) usage.

        Returns:
            A Task object based on the proposal result.
        """
        if not prompt:
            logger.error(err := "Prompt must be provided.")
            raise ValueError(err)

        return await self.propose(Task, prompt, **kwargs)


class HandleTask(ToolBoxUsage, ABC):
    """A class that handles a task based on a task object."""

    async def draft_tool_usage_code(
        self,
        task: Task,
        tools: List[Tool],
        data: Dict[str, Any],
        **kwargs: Unpack[ValidateKwargs],
    ) -> Optional[Tuple[CodeType, List[str]]]:
        """Asynchronously drafts the tool usage code for a task based on a given task object and tools."""
        logger.info(f"Drafting tool usage code for task: {task.briefing}")

        if not tools:
            err = "Tools must be provided to draft the tool usage code."
            logger.error(err)
            raise ValueError(err)

        def _validator(response: str) -> Tuple[CodeType, List[str]] | None:
            if (source := PythonCapture.convert_with(response, lambda resp: compile(resp, "<string>", "exec"))) and (
                to_extract := JsonCapture.convert_with(response, ujson.loads)
            ):
                return source, to_extract

            return None

        q = TEMPLATE_MANAGER.render_template(
            capabilities_config.draft_tool_usage_code_template,
            {
                "data_module_name": CONFIG.toolbox.data_module_name,
                "tool_module_name": CONFIG.toolbox.tool_module_name,
                "task": task.briefing,
                "deps": task.dependencies_prompt,
                "tools": [{"name": t.name, "briefing": t.briefing} for t in tools],
                "data": data,
            },
        )
        logger.debug(f"Code Drafting Question: \n{q}")
        return await self.aask_validate(
            question=q,
            validator=_validator,
            **kwargs,
        )

    async def handle_fine_grind(
        self,
        task: Task,
        data: Dict[str, Any],
        box_choose_kwargs: Optional[ChooseKwargs] = None,
        tool_choose_kwargs: Optional[ChooseKwargs] = None,
        **kwargs: Unpack[ValidateKwargs],
    ) -> Optional[Tuple]:
        """Asynchronously handles a task based on a given task object and parameters."""
        logger.info(f"Handling task: \n{task.briefing}")

        tools = await self.gather_tools_fine_grind(task, box_choose_kwargs, tool_choose_kwargs)
        logger.info(f"Gathered {[t.name for t in tools]}")

        if tools and (pack := await self.draft_tool_usage_code(task, tools, data, **kwargs)):
            executor = ToolExecutor(candidates=tools, data=data)

            code, to_extract = pack
            cxt = executor.execute(code)
            if to_extract:
                return tuple(cxt.get(k) for k in to_extract)

        return None

    async def handle(self, task: Task, data: Dict[str, Any], **kwargs: Unpack[ValidateKwargs]) -> Optional[Tuple]:
        """Asynchronously handles a task based on a given task object and parameters."""
        return await self.handle_fine_grind(task, data, **kwargs)


class DispatchTask(LLMUsage, ABC):
    """A class that dispatches a task based on a task object."""

    async def dispatch_task[T](
        self,
        task: Task[T],
        candidates: Mapping[str, WithBriefing],
        **kwargs: Unpack[ValidateKwargs[List[T]]],
    ) -> T:
        """Asynchronously dispatches a task to an appropriate delegate based on candidate selection.

        This method uses a template to render instructions for selecting the most suitable candidate,
        then delegates the task to that selected candidate by resolving its namespace.

        Parameters:
            task: The task object to be dispatched. It must support delegation.
            candidates: A mapping of identifiers to WithBriefing instances representing available delegates.
                        Each key is a unique identifier and the corresponding value contains briefing details.
            **kwargs: Keyword arguments unpacked from ValidateKwargs[List[T]], typically used for LLM configuration.

        Returns:
            The result of the delegated task execution, which is of generic type T.

        Raises:
            ValueError: If no valid target is picked or if delegation fails.
            KeyError: If the selected target does not exist in the reverse mapping.
        """
        inst = TEMPLATE_MANAGER.render_template(
            capabilities_config.dispatch_task_template,
            {"task": task.briefing, "candidates": [wb.name for wb in candidates.values()]},
        )

        rev_mapping = {wb.name: ns for (ns, wb) in candidates.items()}

        target = await self.apick(inst, list(candidates.values()), **kwargs)

        target_namespace = rev_mapping[target.name]
        return await task.delegate(target_namespace)
