"""Co-validation capability for LLMs."""

from asyncio import gather
from typing import Callable, List, Optional, Union, Unpack, overload

from fabricatio import TEMPLATE_MANAGER
from fabricatio.config import configs
from fabricatio.journal import logger
from fabricatio.models.kwargs_types import GenerateKwargs
from fabricatio.models.usages import LLMUsage


class CoValidate(LLMUsage):
    """Class that represents a co-validation capability using multiple LLMs.

    This class provides methods to validate responses by attempting multiple approaches:
    1. Using the primary LLM to generate a response
    2. Using a secondary (co-) model to refine responses that fail validation
    3. Trying multiple times if needed
    """

    @overload
    async def aask_covalidate[T](
        self,
        question: str,
        validator: Callable[[str], T | None],
        co_model: Optional[str] = None,
        co_temperature: Optional[float] = None,
        co_top_p: Optional[float] = None,
        co_max_tokens: Optional[int] = None,
        max_validations: int = 2,
        default: None = None,
        **kwargs: Unpack[GenerateKwargs],
    ) -> T | None: ...

    @overload
    async def aask_covalidate[T](
        self,
        question: str,
        validator: Callable[[str], T | None],
        co_model: Optional[str] = None,
        co_temperature: Optional[float] = None,
        co_top_p: Optional[float] = None,
        co_max_tokens: Optional[int] = None,
        max_validations: int = 2,
        default: T = ...,
        **kwargs: Unpack[GenerateKwargs],
    ) -> T: ...

    @overload
    async def aask_covalidate[T](
        self,
        question: List[str],
        validator: Callable[[str], T | None],
        co_model: Optional[str] = None,
        co_temperature: Optional[float] = None,
        co_top_p: Optional[float] = None,
        co_max_tokens: Optional[int] = None,
        max_validations: int = 2,
        default: None = None,
        **kwargs: Unpack[GenerateKwargs],
    ) -> List[T | None]: ...

    @overload
    async def aask_covalidate[T](
        self,
        question: List[str],
        validator: Callable[[str], T | None],
        co_model: Optional[str] = None,
        co_temperature: Optional[float] = None,
        co_top_p: Optional[float] = None,
        co_max_tokens: Optional[int] = None,
        max_validations: int = 2,
        default: T = ...,
        **kwargs: Unpack[GenerateKwargs],
    ) -> List[T]: ...

    async def aask_covalidate[T](
        self,
        question: Union[str, List[str]],
        validator: Callable[[str], T | None],
        co_model: Optional[str] = None,
        co_temperature: Optional[float] = None,
        co_top_p: Optional[float] = None,
        co_max_tokens: Optional[int] = None,
        max_validations: int = 2,
        default: Optional[T] = None,
        **kwargs: Unpack[GenerateKwargs],
    ) -> Union[T | None, List[T | None]]:
        """Ask the LLM with co-validation to obtain a validated response.

        This method attempts to generate a response that passes validation using two approaches:
        1. First, it asks the primary LLM using the original question
        2. If validation fails, it uses a secondary (co-) model with a template to improve the response
        3. The process repeats up to max_validations times

        Args:
            question: String question or list of questions to ask
            validator: Function that validates responses, returns result or None if invalid
            co_model: Optional model name for the co-validator
            co_temperature: Optional temperature setting for the co-validator
            co_top_p: Optional top_p setting for the co-validator
            co_max_tokens: Optional maximum tokens for the co-validator response
            max_validations: Maximum number of validation attempts
            default: Default value to return if validation fails
            **kwargs: Additional keyword arguments passed to aask method

        Returns:
            The validated result (T) or default if validation fails.
            If input is a list of questions, returns a list of results.
        """

        async def validate_single_question(q: str) -> Optional[T]:
            """Process a single question with validation attempts."""
            validation_kwargs = kwargs.copy()

            for lap in range(max_validations):
                try:
                    # First attempt: direct question to primary model
                    response = await self.aask(question=q, **validation_kwargs)
                    if response and (validated := validator(response)):
                        logger.debug(f"Successfully validated the primary response at {lap}th attempt.")
                        return validated

                    # Second attempt: use co-model with validation template
                    co_prompt = TEMPLATE_MANAGER.render_template(
                        configs.templates.co_validation_template,
                        {"original_q": q, "original_a": response},
                    )
                    co_response = await self.aask(
                        question=co_prompt,
                        model=co_model,
                        temperature=co_temperature,
                        top_p=co_top_p,
                        max_tokens=co_max_tokens,
                    )

                    if co_response and (validated := validator(co_response)):
                        logger.debug(f"Successfully validated the co-response at {lap}th attempt.")
                        return validated

                except Exception as e:  # noqa: BLE001
                    logger.error(f"Error during validation: \n{e}")
                    break

                # Disable caching for subsequent attempts
                if not validation_kwargs.get("no_cache"):
                    validation_kwargs["no_cache"] = True
                    logger.debug("Disabled cache for the next attempt")

            if default is None:
                logger.error(f"Failed to validate the response after {max_validations} attempts.")
            return default

        # Handle single question or list of questions
        if isinstance(question, str):
            return await validate_single_question(question)

        # Process multiple questions in parallel
        return await gather(*[validate_single_question(q) for q in question])
