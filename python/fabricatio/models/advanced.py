"""A module for advanced models and functionalities."""

from types import CodeType
from typing import Any, Dict, List, Optional, Set, Tuple, Unpack

import orjson
from fabricatio._rust_instances import template_manager
from fabricatio.config import configs
from fabricatio.models.generic import WithBriefing
from fabricatio.models.kwargs_types import ChooseKwargs, ValidateKwargs
from fabricatio.models.task import Task
from fabricatio.models.tool import Tool, ToolExecutor
from fabricatio.models.usages import LLMUsage, ToolBoxUsage
from fabricatio.parser import JsonCapture, PythonCapture
from loguru import logger
from pydantic import ValidationError


class ProposeTask(WithBriefing, LLMUsage):
    """A class that proposes a task based on a prompt."""

    async def propose[T](
        self,
        prompt: str,
        **kwargs: Unpack[ValidateKwargs],
    ) -> Task[T]:
        """Asynchronously proposes a task based on a given prompt and parameters.

        Parameters:
            prompt: The prompt text for proposing a task, which is a string that must be provided.
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
            **kwargs,
        )


class HandleTask(WithBriefing, ToolBoxUsage):
    """A class that handles a task based on a task object."""

    async def draft_tool_usage_code(
        self,
        task: Task,
        tools: List[Tool],
        data: Dict[str, Any],
        **kwargs: Unpack[ValidateKwargs],
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
        box_choose_kwargs: Optional[ChooseKwargs] = None,
        tool_choose_kwargs: Optional[ChooseKwargs] = None,
        **kwargs: Unpack[ValidateKwargs],
    ) -> Optional[Tuple]:
        """Asynchronously handles a task based on a given task object and parameters."""
        logger.info(f"Handling task: \n{task.briefing}")

        tools = await self.gather_tools_fine_grind(task, box_choose_kwargs, tool_choose_kwargs)
        logger.info(f"{self.name} have gathered {[t.name for t in tools]}")

        if tools:
            executor = ToolExecutor(candidates=tools, data=data)
            code, to_extract = await self.draft_tool_usage_code(task, tools, data, **kwargs)

            cxt = executor.execute(code)
            if to_extract:
                return tuple(cxt.get(k) for k in to_extract)

        return None

    async def handle(self, task: Task, data: Dict[str, Any], **kwargs: Unpack[ValidateKwargs]) -> Optional[Tuple]:
        """Asynchronously handles a task based on a given task object and parameters."""
        return await self.handle_fin_grind(task, data, **kwargs)


class GiveRating(WithBriefing, LLMUsage):
    """A class that provides functionality to rate tasks based on a rating manual and score range."""

    async def rate_fine_grind(
        self,
        to_rate: str,
        rating_manual: Dict[str, str],
        score_range: Tuple[float, float],
        **kwargs: Unpack[ValidateKwargs],
    ) -> Dict[str, float]:
        """Rates a given task based on a rating manual and score range.

        Args:
            to_rate: The task to be rated.
            rating_manual: A dictionary containing the rating criteria.
            score_range: A tuple representing the valid score range.
            **kwargs: Additional keyword arguments for the LLM usage.

        Returns:
            A dictionary with the ratings for each dimension.
        """

        def _validator(response: str) -> Dict[str, float] | None:
            if (
                (json_data := JsonCapture.convert_with(response, orjson.loads)) is not None
                and isinstance(json_data, dict)
                and json_data.keys() == rating_manual.keys()
                and all(isinstance(v, float) for v in json_data.values())
                and all(score_range[0] <= v <= score_range[1] for v in json_data.values())
            ):
                return json_data
            return None

        return await self.aask_validate(
            question=(
                template_manager.render_template(
                    configs.templates.rate_fine_grind_template,
                    {
                        "to_rate": to_rate,
                        "min_score": score_range[0],
                        "max_score": score_range[1],
                        "rating_manual": rating_manual,
                    },
                )
            ),
            validator=_validator,
            system_message=f"# your personal briefing: \n{self.briefing}",
            **kwargs,
        )

    async def rate(
        self,
        to_rate: str,
        topic: str,
        dimensions: Set[str],
        score_range: Tuple[float, float] = (0.0, 1.0),
        **kwargs: Unpack[ValidateKwargs],
    ) -> Dict[str, float]:
        """Rates a task based on a topic and dimensions. this function will automatically draft a rating manual based on the topic and dimensions.

        Args:
            to_rate: The task to be rated.
            topic: The topic related to the task.
            dimensions: A set of dimensions for rating.
            score_range: A tuple representing the valid score range
            **kwargs: Additional keyword arguments for the LLM usage.

        Returns:
            A dictionary with the ratings for each dimension.
        """
        manual = await self.draft_rating_manual(topic, dimensions, **kwargs)
        return await self.rate_fine_grind(to_rate, manual, score_range, **kwargs)

    async def draft_rating_manual(
        self, topic: str, dimensions: Set[str], **kwargs: Unpack[ValidateKwargs]
    ) -> Dict[str, str]:
        """Drafts a rating manual based on a topic and dimensions.

        Args:
            topic: The topic for the rating manual.
            dimensions: A set of dimensions for the rating manual.
            **kwargs: Additional keyword arguments for the LLM usage.

        Returns:
            A dictionary representing the drafted rating manual.
        """

        def _validator(response: str) -> Dict[str, str] | None:
            if (
                (json_data := JsonCapture.convert_with(response, orjson.loads)) is not None
                and isinstance(json_data, dict)
                and json_data.keys() == dimensions
                and all(isinstance(v, str) for v in json_data.values())
            ):
                return json_data
            return None

        return await self.aask_validate(
            question=(
                template_manager.render_template(
                    configs.templates.draft_rating_manual_template,
                    {
                        "topic": topic,
                        "dimensions": dimensions,
                    },
                )
            ),
            validator=_validator,
            system_message=f"# your personal briefing: \n{self.briefing}",
            **kwargs,
        )
