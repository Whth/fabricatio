"""A module for advanced models and functionalities."""

from types import CodeType
from typing import Any, Dict, List, Optional, Tuple, Unpack

import orjson
from fabricatio._rust_instances import template_manager
from fabricatio.config import configs
from fabricatio.models.generic import WithBriefing
from fabricatio.models.kwargs_types import LLMKwargs
from fabricatio.models.task import Task
from fabricatio.models.tool import Tool, ToolExecutor
from fabricatio.models.usages import LLMUsage, ToolBoxUsage
from fabricatio.parser import JsonCapture, PythonCapture
from loguru import logger
from pydantic import PositiveInt, ValidationError


class ProposeTask(WithBriefing, LLMUsage):
    """A class that proposes a task based on a prompt."""

    async def propose[T](
        self,
        prompt: str,
        max_validations: PositiveInt = 2,
        **kwargs: Unpack[LLMKwargs],
    ) -> Task[T]:
        """Asynchronously proposes a task based on a given prompt and parameters.

        Parameters:
            prompt: The prompt text for proposing a task, which is a string that must be provided.
            max_validations: The maximum number of validations allowed, default is 2.
            **kwargs: The keyword arguments for the LLM (Large Language Model) usage.

        Returns:
            A Task object based on the proposal result.
        """
        if not prompt:
            err = f"{self.name}: Prompt must be provided."
            logger.error(err)
            raise ValueError(err)

        def _validate_json(response: str) -> None | Task:
            try:
                cap = JsonCapture.capture(response)
                logger.debug(f"Response: \n{response}")
                logger.info(f"Captured JSON: \n{cap}")
                return Task.model_validate_json(cap)
            except ValidationError as e:
                logger.error(f"Failed to parse task from JSON: {e}")
                return None

        template_data = {"prompt": prompt, "json_example": Task.json_example()}
        return await self.aask_validate(
            question=template_manager.render_template(configs.templates.propose_task_template, template_data),
            validator=_validate_json,
            system_message=f"# your personal briefing: \n{self.briefing}",
            max_validations=max_validations,
            **kwargs,
        )


class HandleTask(WithBriefing, ToolBoxUsage):
    """A class that handles a task based on a task object."""

    async def draft_tool_usage_code(
        self,
        task: Task,
        tools: List[Tool],
        data: Dict[str, Any],
        **kwargs: Unpack[LLMKwargs],
    ) -> Tuple[CodeType, List[str]]:
        """Asynchronously drafts the tool usage code for a task based on a given task object and tools."""
        logger.info(f"Drafting tool usage code for task: {task.briefing}")

        if not tools:
            err = f"{self.name}: Tools must be provided to draft the tool usage code."
            logger.error(err)
            raise ValueError(err)

        def _validator(response: str) -> Tuple[CodeType, List[str]] | None:
            if (source := PythonCapture.convert_with(response, lambda resp: compile(resp, "<string>", "exec"))) and (
                to_extract := JsonCapture.convert_with(response, orjson.loads)
            ):
                return source, to_extract

            return None

        q = template_manager.render_template(
            configs.templates.draft_tool_usage_code_template,
            {
                "data_module_name": configs.toolbox.data_module_name,
                "tool_module_name": configs.toolbox.tool_module_name,
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
            system_message=f"# your personal briefing: \n{self.briefing}",
            **kwargs,
        )

    async def handle_fin_grind(
        self,
        task: Task,
        data: Dict[str, Any],
        **kwargs: Unpack[LLMKwargs],
    ) -> Optional[Tuple]:
        """Asynchronously handles a task based on a given task object and parameters."""
        logger.info(f"Handling task: \n{task.briefing}")

        tools = await self.gather_tools(task)
        logger.info(f"{self.name} have gathered {[t.name for t in tools]}")

        if tools:
            executor = ToolExecutor(candidates=tools, data=data)
            code, to_extract = await self.draft_tool_usage_code(task, tools, data, **kwargs)

            cxt = executor.execute(code)
            if to_extract:
                return tuple(cxt.get(k) for k in to_extract)

        return None
