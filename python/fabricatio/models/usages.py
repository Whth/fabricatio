"""This module contains classes that manage the usage of language models and tools in tasks."""

from typing import Callable, Dict, Iterable, List, NotRequired, Optional, Self, Set, TypedDict, Union, Unpack

import litellm
import orjson
from fabricatio._rust_instances import template_manager
from fabricatio.config import configs
from fabricatio.journal import logger
from fabricatio.models.generic import Base, WithBriefing
from fabricatio.models.task import Task
from fabricatio.models.tool import ToolBox
from fabricatio.models.utils import Messages
from fabricatio.parser import JsonCapture
from litellm.types.utils import Choices, ModelResponse, StreamingChoices
from pydantic import Field, HttpUrl, NonNegativeFloat, NonNegativeInt, PositiveInt, SecretStr


class LLMKwargs(TypedDict):
    """A type representing the keyword arguments for the LLM (Large Language Model) usage."""

    model: NotRequired[str]
    temperature: NotRequired[NonNegativeFloat]
    stop: NotRequired[str | List[str]]
    top_p: NotRequired[NonNegativeFloat]
    max_tokens: NotRequired[PositiveInt]
    stream: NotRequired[bool]
    timeout: NotRequired[PositiveInt]
    max_retries: NotRequired[PositiveInt]


class LLMUsage(Base):
    """Class that manages LLM (Large Language Model) usage parameters and methods."""

    llm_api_endpoint: Optional[HttpUrl] = None
    """The OpenAI API endpoint."""

    llm_api_key: Optional[SecretStr] = None
    """The OpenAI API key."""

    llm_timeout: Optional[PositiveInt] = None
    """The timeout of the LLM model."""

    llm_max_retries: Optional[PositiveInt] = None
    """The maximum number of retries."""

    llm_model: Optional[str] = None
    """The LLM model name."""

    llm_temperature: Optional[NonNegativeFloat] = None
    """The temperature of the LLM model."""

    llm_stop_sign: Optional[str | List[str]] = None
    """The stop sign of the LLM model."""

    llm_top_p: Optional[NonNegativeFloat] = None
    """The top p of the LLM model."""

    llm_generation_count: Optional[PositiveInt] = None
    """The number of generations to generate."""

    llm_stream: Optional[bool] = None
    """Whether to stream the LLM model's response."""

    llm_max_tokens: Optional[PositiveInt] = None
    """The maximum number of tokens to generate."""

    async def aquery(
        self,
        messages: List[Dict[str, str]],
        n: PositiveInt | None = None,
        **kwargs: Unpack[LLMKwargs],
    ) -> ModelResponse:
        """Asynchronously queries the language model to generate a response based on the provided messages and parameters.

        Args:
            messages (List[Dict[str, str]]): A list of messages, where each message is a dictionary containing the role and content of the message.
            model (str | None): The name of the model to use. If not provided, the default model will be used.
            temperature (NonNegativeFloat | None): Controls the randomness of the output. Lower values make the output more deterministic.
            stop (str | None): A sequence at which to stop the generation of the response.
            top_p (NonNegativeFloat | None): Controls the diversity of the output through nucleus sampling.
            max_tokens (PositiveInt | None): The maximum number of tokens to generate in the response.
            n (PositiveInt | None): The number of responses to generate.
            stream (bool | None): Whether to receive the response in a streaming fashion.
            timeout (PositiveInt | None): The timeout duration for the request.
            max_retries (PositiveInt | None): The maximum number of retries in case of failure.

        Returns:
            ModelResponse: An object containing the generated response and other metadata from the model.
        """
        # Call the underlying asynchronous completion function with the provided and default parameters
        return await litellm.acompletion(
            messages=messages,
            n=n or self.llm_generation_count or configs.llm.generation_count,
            model=kwargs.get("model") or self.llm_model or configs.llm.model,
            temperature=kwargs.get("temperature") or self.llm_temperature or configs.llm.temperature,
            stop=kwargs.get("stop") or self.llm_stop_sign or configs.llm.stop_sign,
            top_p=kwargs.get("top_p") or self.llm_top_p or configs.llm.top_p,
            max_tokens=kwargs.get("max_tokens") or self.llm_max_tokens or configs.llm.max_tokens,
            stream=kwargs.get("stream") or self.llm_stream or configs.llm.stream,
            timeout=kwargs.get("timeout") or self.llm_timeout or configs.llm.timeout,
            max_retries=kwargs.get("max_retries") or self.llm_max_retries or configs.llm.max_retries,
            api_key=self.llm_api_key.get_secret_value() if self.llm_api_key else configs.llm.api_key.get_secret_value(),
            base_url=self.llm_api_endpoint.unicode_string()
            if self.llm_api_endpoint
            else configs.llm.api_endpoint.unicode_string(),
        )

    async def ainvoke(
        self,
        question: str,
        system_message: str = "",
        n: PositiveInt | None = None,
        **kwargs: Unpack[LLMKwargs],
    ) -> List[Choices | StreamingChoices]:
        """Asynchronously invokes the language model with a question and optional system message.

        Args:
            question (str): The question to ask the model.
            system_message (str): The system message to provide context to the model.
            model (str | None): The name of the model to use. If not provided, the default model will be used.
            temperature (NonNegativeFloat | None): Controls the randomness of the output. Lower values make the output more deterministic.
            stop (str | None): A sequence at which to stop the generation of the response.
            top_p (NonNegativeFloat | None): Controls the diversity of the output through nucleus sampling.
            max_tokens (PositiveInt | None): The maximum number of tokens to generate in the response.
            n (PositiveInt | None): The number of responses to generate.
            stream (bool | None): Whether to receive the response in a streaming fashion.
            timeout (PositiveInt | None): The timeout duration for the request.
            max_retries (PositiveInt | None): The maximum number of retries in case of failure.

        Returns:
            List[Choices | StreamingChoices]: A list of choices or streaming choices from the model response.
        """
        return (
            await self.aquery(
                messages=Messages().add_system_message(system_message).add_user_message(question),
                n=n,
                **kwargs,
            )
        ).choices

    async def aask(
        self,
        question: str,
        system_message: str = "",
        **kwargs: Unpack[LLMKwargs],
    ) -> str:
        """Asynchronously asks the language model a question and returns the response content.

        Args:
            question (str): The question to ask the model.
            system_message (str): The system message to provide context to the model.
            model (str | None): The name of the model to use. If not provided, the default model will be used.
            temperature (NonNegativeFloat | None): Controls the randomness of the output. Lower values make the output more deterministic.
            stop (str | None): A sequence at which to stop the generation of the response.
            top_p (NonNegativeFloat | None): Controls the diversity of the output through nucleus sampling.
            max_tokens (PositiveInt | None): The maximum number of tokens to generate in the response.
            stream (bool | None): Whether to receive the response in a streaming fashion.
            timeout (PositiveInt | None): The timeout duration for the request.
            max_retries (PositiveInt | None): The maximum number of retries in case of failure.

        Returns:
            str: The content of the model's response message.
        """
        return (
            (
                await self.ainvoke(
                    n=1,
                    question=question,
                    system_message=system_message,
                    **kwargs,
                )
            )
            .pop()
            .message.content
        )

    async def aask_validate[T](
        self,
        question: str,
        validator: Callable[[str], T | None],
        max_validations: PositiveInt = 2,
        system_message: str = "",
        **kwargs: Unpack[LLMKwargs],
    ) -> T:
        """Asynchronously ask a question and validate the response using a given validator.

        Args:
            question (str): The question to ask.
            validator (Callable[[str], T | None]): A function to validate the response.
            max_validations (PositiveInt): Maximum number of validation attempts.
            system_message (str): System message to include in the request.
            model (str | None): The model to use for the request.
            temperature (NonNegativeFloat | None): Temperature setting for the request.
            stop (str | None): Stop sequence for the request.
            top_p (NonNegativeFloat | None): Top-p sampling parameter.
            max_tokens (PositiveInt | None): Maximum number of tokens in the response.
            stream (bool | None): Whether to stream the response.
            timeout (PositiveInt | None): Timeout for the request.
            max_retries (PositiveInt | None): Maximum number of retries for the request.

        Returns:
            T: The validated response.

        Raises:
            ValueError: If the response fails to validate after the maximum number of attempts.
        """
        for _ in range(max_validations):
            if (
                response := await self.aask(
                    question=question,
                    system_message=system_message,
                    **kwargs,
                )
            ) and (validated := validator(response)):
                return validated
        raise ValueError("Failed to validate the response.")

    async def achoose[T: WithBriefing](
        self,
        instruction: str,
        choices: List[T],
        k: NonNegativeInt = 0,
        max_validations: PositiveInt = 2,
        system_message: str = "",
        **kwargs: Unpack[LLMKwargs],
    ) -> List[T]:
        """Asynchronously executes a multi-choice decision-making process, generating a prompt based on the instruction and options, and validates the returned selection results.

        Args:
            instruction: The user-provided instruction/question description.
            choices: A list of candidate options, requiring elements to have `name` and `briefing` fields.
            k: The number of choices to select, 0 means infinite.
            max_validations: Maximum number of validation failures, default is 2.
            system_message: Custom system-level prompt, defaults to an empty string.
            model: The name of the LLM model to use.
            temperature: Sampling temperature to control randomness in generation.
            stop: Stop condition string or list for generation.
            top_p: Core sampling probability threshold.
            max_tokens: Maximum token limit for the generated result.
            stream: Whether to enable streaming response mode.
            timeout: Request timeout in seconds.
            max_retries: Maximum number of retries.

        Returns:
            List[T]: The final validated selection result list, with element types matching the input `choices`.

        Important:
            - Uses a template engine to generate structured prompts.
            - Ensures response compliance through JSON parsing and format validation.
            - Relies on `aask_validate` to implement retry mechanisms with validation.
        """
        prompt = template_manager.render_template(
            "make_choice",
            {
                "instruction": instruction,
                "options": [m.model_dump(include={"name", "briefing"}) for m in choices],
                "k": k,
            },
        )
        names = [c.name for c in choices]

        def _validate(response: str) -> List[T] | None:
            ret = JsonCapture.convert_with(response, orjson.loads)
            if not isinstance(ret, List) or len(ret) != k:
                return None
            if any(n not in names for n in ret):
                return None
            return ret

        return await self.aask_validate(
            question=prompt,
            validator=_validate,
            max_validations=max_validations,
            system_message=system_message,
            **kwargs,
        )

    async def ajudge(
        self,
        prompt: str,
        affirm_case: str = "",
        deny_case: str = "",
        max_validations: PositiveInt = 2,
        system_message: str = "",
        **kwargs: Unpack[LLMKwargs],
    ) -> bool:
        """Asynchronously judges a prompt using AI validation.

        Args:
            prompt (str): The input prompt to be judged.
            affirm_case (str, optional): The affirmative case for the AI model. Defaults to "".
            deny_case (str, optional): The negative case for the AI model. Defaults to "".
            max_validations (PositiveInt, optional): Maximum number of validation attempts. Defaults to 2.
            system_message (str, optional): System message for the AI model. Defaults to "".
            model (str | None, optional): AI model to use. Defaults to None.
            temperature (NonNegativeFloat | None, optional): Sampling temperature. Defaults to None.
            stop (str | List[str] | None, optional): Stop sequences. Defaults to None.
            top_p (NonNegativeFloat | None, optional): Nucleus sampling parameter. Defaults to None.
            max_tokens (PositiveInt | None, optional): Maximum number of tokens to generate. Defaults to None.
            stream (bool | None, optional): Whether to stream the response. Defaults to None.
            timeout (PositiveInt | None, optional): Timeout in seconds. Defaults to None.
            max_retries (PositiveInt | None, optional): Maximum number of retries. Defaults to None.

        Returns:
            bool: The judgment result (True or False) based on the AI's response.

        Notes:
            The method uses an internal validator to ensure the response is a boolean value.
            If the response cannot be converted to a boolean, it will return None.
        """

        def _validate(response: str) -> bool | None:
            ret = JsonCapture.convert_with(response, orjson.loads)
            if not isinstance(ret, bool):
                return None
            return ret

        return await self.aask_validate(
            question=template_manager.render_template(
                "make_judgment", {"prompt": prompt, "affirm_case": affirm_case, "deny_case": deny_case}
            ),
            validator=_validate,
            max_validations=max_validations,
            system_message=system_message,
            **kwargs,
        )

    def fallback_to(self, other: "LLMUsage") -> Self:
        """Fallback to another instance's attribute values if the current instance's attributes are None.

        Args:
            other (LLMUsage): Another instance from which to copy attribute values.

        Returns:
            Self: The current instance, allowing for method chaining.
        """
        # Iterate over the attribute names and copy values from 'other' to 'self' where applicable
        # noinspection PydanticTypeChecker,PyTypeChecker
        for attr_name in LLMUsage.model_fields:
            # Copy the attribute value from 'other' to 'self' only if 'self' has None and 'other' has a non-None value
            if getattr(self, attr_name) is None and (attr := getattr(other, attr_name)) is not None:
                setattr(self, attr_name, attr)

        # Return the current instance to allow for method chaining
        return self

    def hold_to(self, others: Union["LLMUsage", Iterable["LLMUsage"]]) -> Self:
        """Hold to another instance's attribute values if the current instance's attributes are None.

        Args:
            others (LLMUsage | Iterable[LLMUsage]): Another instance or iterable of instances from which to copy attribute values.

        Returns:
            Self: The current instance, allowing for method chaining.
        """
        for other in others:
            # noinspection PyTypeChecker,PydanticTypeChecker
            for attr_name in LLMUsage.model_fields:
                if (attr := getattr(self, attr_name)) is not None and getattr(other, attr_name) is None:
                    setattr(other, attr_name, attr)


class ToolBoxUsage(LLMUsage):
    """A class representing the usage of tools in a task."""

    toolboxes: Set[ToolBox] = Field(default_factory=set)
    """A set of toolboxes used by the instance."""

    async def choose_toolboxes(
        self,
        task: Task,
        k: NonNegativeInt = 0,
        max_validations: PositiveInt = 2,
        system_message: str = "",
        **kwargs: Unpack[LLMKwargs],
    ) -> List[ToolBox]:
        """Asynchronously executes a multi-choice decision-making process to choose toolboxes."""
        if not self.toolboxes:
            logger.warning("No toolboxes available.")
            return []
        return await self.achoose(
            instruction=task.briefing,
            choices=list(self.toolboxes),
            k=k,
            max_validations=max_validations,
            system_message=system_message,
            **kwargs,
        )

    async def choose_tools(self, task: Task):
        # TODO Implement this method
        pass

    @property
    def available_toolbox_names(self) -> List[str]:
        """Return a list of available toolbox names."""
        return [toolbox.name for toolbox in self.toolboxes]

    def supply_tools_from(self, others: Union["ToolBoxUsage", Iterable["ToolBoxUsage"]]) -> Self:
        """Supplies tools from other ToolUsage instances to this instance.

        Args:
            others ("ToolUsage" | Iterable["ToolUsage"]): A single ToolUsage instance or an iterable of ToolUsage instances
                from which to take tools.

        Returns:
            Self: The current ToolUsage instance with updated tools.
        """
        if isinstance(others, ToolBoxUsage):
            others = [others]
        for other in others:
            self.toolboxes.update(other.toolboxes)
        return self

    def provide_tools_to(self, others: Union["ToolBoxUsage", Iterable["ToolBoxUsage"]]) -> Self:
        """Provides tools from this instance to other ToolUsage instances.

        Args:
            others ("ToolUsage" | Iterable["ToolUsage"]): A single ToolUsage instance or an iterable of ToolUsage instances
                to which to provide tools.

        Returns:
            Self: The current ToolUsage instance.
        """
        if isinstance(others, ToolBoxUsage):
            others = [others]
        for other in others:
            other.toolboxes.update(self.toolboxes)
        return self
