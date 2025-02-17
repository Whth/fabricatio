"""A module for advanced models and functionalities."""

from typing import List

from fabricatio._rust_instances import template_manager
from fabricatio.models.generic import WithBriefing
from fabricatio.models.task import Task
from fabricatio.models.usages import LLMUsage, ToolBoxUsage
from fabricatio.parser import JsonCapture
from loguru import logger
from pydantic import NonNegativeFloat, PositiveInt, ValidationError


class ProposeTask(LLMUsage, WithBriefing):
    """A class that proposes a task based on a prompt."""

    async def propose(
        self,
        prompt: str,
        max_validations: PositiveInt = 2,
        model: str | None = None,
        temperature: NonNegativeFloat | None = None,
        stop: str | List[str] | None = None,
        top_p: NonNegativeFloat | None = None,
        max_tokens: PositiveInt | None = None,
        stream: bool | None = None,
        timeout: PositiveInt | None = None,
        max_retries: PositiveInt | None = None,
    ) -> Task:
        """Asynchronously proposes a task based on a given prompt and parameters.

        Parameters:
            prompt: The prompt text for proposing a task, which is a string that must be provided.
            max_validations: The maximum number of validations allowed, default is 2.
            model: The model to be used, default is None.
            temperature: The sampling temperature, default is None.
            stop: The stop sequence(s) for generation, default is None.
            top_p: The nucleus sampling parameter, default is None.
            max_tokens: The maximum number of tokens to be generated, default is None.
            stream: Whether to stream the output, default is None.
            timeout: The timeout for the operation, default is None.
            max_retries: The maximum number of retries for the operation, default is None.

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
            question=template_manager.render_template("propose_task", template_data),
            validator=_validate_json,
            system_message=f"# your personal briefing: \n{self.briefing}",
            max_validations=max_validations,
            model=model,
            temperature=temperature,
            stop=stop,
            top_p=top_p,
            max_tokens=max_tokens,
            stream=stream,
            timeout=timeout,
            max_retries=max_retries,
        )


class HandleTask(WithBriefing, ToolBoxUsage):
    """A class that handles a task based on a task object."""

    async def handle[T](
        self,
        task: Task[T],
        max_validations: PositiveInt = 2,
        model: str | None = None,
        temperature: NonNegativeFloat | None = None,
        stop: str | List[str] | None = None,
        top_p: NonNegativeFloat | None = None,
        max_tokens: PositiveInt | None = None,
        stream: bool | None = None,
        timeout: PositiveInt | None = None,
        max_retries: PositiveInt | None = None,
    ) -> T:
        """Asynchronously handles a task based on a given task object and parameters."""
        # TODO: Implement the handle method
