"""This module defines generic classes for models in the Fabricatio library."""

from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Self, Union

import litellm
import orjson
from fabricatio._rust_instances import template_manager
from fabricatio.config import configs
from fabricatio.fs.readers import magika
from fabricatio.models.utils import Messages
from fabricatio.parser import JsonCapture
from litellm.types.utils import Choices, ModelResponse, StreamingChoices
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    NonNegativeFloat,
    PositiveInt,
    SecretStr,
)


class Base(BaseModel):
    """Base class for all models with Pydantic configuration."""

    model_config = ConfigDict(use_attribute_docstrings=True)


class Named(Base):
    """Class that includes a name attribute."""

    name: str = Field(frozen=True)
    """The name of the object."""


class Described(Base):
    """Class that includes a description attribute."""

    description: str = Field(default="", frozen=True)
    """The description of the object."""


class WithBriefing(Named, Described):
    """Class that provides a briefing based on the name and description."""

    @property
    def briefing(self) -> str:
        """Get the briefing of the object.

        Returns:
            str: The briefing of the object.
        """
        return f"{self.name}: {self.description}" if self.description else self.name


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
        model: str | None = None,
        temperature: NonNegativeFloat | None = None,
        stop: str | List[str] | None = None,
        top_p: NonNegativeFloat | None = None,
        max_tokens: PositiveInt | None = None,
        n: PositiveInt | None = None,
        stream: bool | None = None,
        timeout: PositiveInt | None = None,
        max_retries: PositiveInt | None = None,
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
            model=model or self.llm_model or configs.llm.model,
            temperature=temperature or self.llm_temperature or configs.llm.temperature,
            stop=stop or self.llm_stop_sign or configs.llm.stop_sign,
            top_p=top_p or self.llm_top_p or configs.llm.top_p,
            max_tokens=max_tokens or self.llm_max_tokens or configs.llm.max_tokens,
            n=n or self.llm_generation_count or configs.llm.generation_count,
            stream=stream or self.llm_stream or configs.llm.stream,
            timeout=timeout or self.llm_timeout or configs.llm.timeout,
            max_retries=max_retries or self.llm_max_retries or configs.llm.max_retries,
            api_key=self.llm_api_key.get_secret_value() if self.llm_api_key else configs.llm.api_key.get_secret_value(),
            base_url=self.llm_api_endpoint.unicode_string()
            if self.llm_api_endpoint
            else configs.llm.api_endpoint.unicode_string(),
        )

    async def ainvoke(
        self,
        question: str,
        system_message: str = "",
        model: str | None = None,
        temperature: NonNegativeFloat | None = None,
        stop: str | List[str] | None = None,
        top_p: NonNegativeFloat | None = None,
        max_tokens: PositiveInt | None = None,
        n: PositiveInt | None = None,
        stream: bool | None = None,
        timeout: PositiveInt | None = None,
        max_retries: PositiveInt | None = None,
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
                model=model,
                temperature=temperature,
                stop=stop,
                top_p=top_p,
                max_tokens=max_tokens,
                n=n,
                stream=stream,
                timeout=timeout,
                max_retries=max_retries,
            )
        ).choices

    async def aask(
        self,
        question: str,
        system_message: str = "",
        model: str | None = None,
        temperature: NonNegativeFloat | None = None,
        stop: str | List[str] | None = None,
        top_p: NonNegativeFloat | None = None,
        max_tokens: PositiveInt | None = None,
        stream: bool | None = None,
        timeout: PositiveInt | None = None,
        max_retries: PositiveInt | None = None,
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
                    model=model,
                    temperature=temperature,
                    stop=stop,
                    top_p=top_p,
                    max_tokens=max_tokens,
                    stream=stream,
                    timeout=timeout,
                    max_retries=max_retries,
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
        model: str | None = None,
        temperature: NonNegativeFloat | None = None,
        stop: str | List[str] | None = None,
        top_p: NonNegativeFloat | None = None,
        max_tokens: PositiveInt | None = None,
        stream: bool | None = None,
        timeout: PositiveInt | None = None,
        max_retries: PositiveInt | None = None,
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
                    model=model,
                    temperature=temperature,
                    stop=stop,
                    top_p=top_p,
                    max_tokens=max_tokens,
                    stream=stream,
                    timeout=timeout,
                    max_retries=max_retries,
                )
            ) and (validated := validator(response)):
                return validated
        raise ValueError("Failed to validate the response.")

    async def achoose[T: WithBriefing](
        self,
        instruction: str,
        choices: List[T],
        max_validations: PositiveInt = 2,
        system_message: str = "",
        model: str | None = None,
        temperature: NonNegativeFloat | None = None,
        stop: str | List[str] | None = None,
        top_p: NonNegativeFloat | None = None,
        max_tokens: PositiveInt | None = None,
        stream: bool | None = None,
        timeout: PositiveInt | None = None,
        max_retries: PositiveInt | None = None,
    ) -> List[T]:
        """Asynchronously executes a multi-choice decision-making process, generating a prompt based on the instruction and options, and validates the returned selection results.

        Args:
            instruction: The user-provided instruction/question description.
            choices: A list of candidate options, requiring elements to have `name` and `briefing` fields.
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
            {"instruction": instruction, "options": [m.model_dump(include={"name", "briefing"}) for m in choices]},
        )
        names = [c.name for c in choices]

        def _validate(response: str) -> List[T] | None:
            cap = JsonCapture.capture(response)
            ret = orjson.loads(cap)
            if not isinstance(ret, List):
                return None
            if any(n not in names for n in ret):
                return None
            return ret

        return await self.aask_validate(
            question=prompt,
            validator=_validate,
            max_validations=max_validations,
            system_message=system_message,
            model=model,
            temperature=temperature,
            stop=stop,
            top_p=top_p,
            max_tokens=max_tokens,
            stream=stream,
            timeout=timeout,
            max_retries=max_retries,
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


class WithJsonExample(Base):
    """Class that provides a JSON schema for the model."""

    @classmethod
    def json_example(cls) -> str:
        """Return a JSON example for the model.

        Returns:
            str: A JSON example for the model.
        """
        return orjson.dumps(
            {field_name: field_info.description for field_name, field_info in cls.model_fields.items()},
            option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS,
        ).decode()


class WithDependency(Base):
    """Class that manages file dependencies."""

    dependencies: List[str] = Field(default_factory=list)
    """The file dependencies of the task, a list of file paths."""

    def add_dependency[P: str | Path](self, dependency: P | List[P]) -> Self:
        """Add a file dependency to the task.

        Args:
            dependency (str | Path | List[str | Path]): The file dependency to add to the task.

        Returns:
            Self: The current instance of the task.
        """
        if not isinstance(dependency, list):
            dependency = [dependency]
        self.dependencies.extend(Path(d).as_posix() for d in dependency)
        return self

    def remove_dependency[P: str | Path](self, dependency: P | List[P]) -> Self:
        """Remove a file dependency from the task.

        Args:
            dependency (str | Path | List[str | Path]): The file dependency to remove from the task.

        Returns:
            Self: The current instance of the task.
        """
        if not isinstance(dependency, list):
            dependency = [dependency]
        for d in dependency:
            self.dependencies.remove(Path(d).as_posix())
        return self

    def generate_prompt(self) -> str:
        """Generate a prompt for the task based on the file dependencies.

        Returns:
            str: The generated prompt for the task.
        """
        contents = [Path(d).read_text("utf-8") for d in self.dependencies]
        recognized = [magika.identify_path(c) for c in contents]
        out = ""
        for r, p, c in zip(recognized, self.dependencies, contents, strict=False):
            out += f"---\n\n> {p}\n```{r.dl.ct_label}\n{c}\n```\n\n"
        return out
