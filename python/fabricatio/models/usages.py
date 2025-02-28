"""This module contains classes that manage the usage of language models and tools in tasks."""

from asyncio import gather
from typing import Callable, Dict, Iterable, List, Optional, Self, Set, Union, Unpack, overload

import asyncstdlib
import litellm
import orjson
from fabricatio._rust_instances import template_manager
from fabricatio.config import configs
from fabricatio.journal import logger
from fabricatio.models.generic import Base, WithBriefing
from fabricatio.models.kwargs_types import ChooseKwargs, EmbeddingKwargs, GenerateKwargs, LLMKwargs
from fabricatio.models.task import Task
from fabricatio.models.tool import Tool, ToolBox
from fabricatio.models.utils import Messages, MilvusData
from fabricatio.parser import JsonCapture
from litellm import stream_chunk_builder
from litellm.types.utils import (
    Choices,
    EmbeddingResponse,
    ModelResponse,
    StreamingChoices,
)
from litellm.utils import CustomStreamWrapper
from pydantic import Field, HttpUrl, NonNegativeFloat, NonNegativeInt, PositiveInt, SecretStr


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

    async def aembedding(
        self,
        input_text: List[str],
        model: Optional[str] = None,
        dimensions: Optional[int] = None,
        timeout: Optional[PositiveInt] = None,
        caching: Optional[bool] = False,
    ) -> EmbeddingResponse:
        """Asynchronously generates embeddings for the given input text.

        Args:
            input_text (List[str]): A list of strings to generate embeddings for.
            model (Optional[str]): The model to use for embedding. Defaults to the instance's `llm_model` or the global configuration.
            dimensions (Optional[int]): The dimensions of the embedding. Defaults to None.
            timeout (Optional[PositiveInt]): The timeout for the embedding request. Defaults to the instance's `llm_timeout` or the global configuration.
            caching (Optional[bool]): Whether to cache the embedding result. Defaults to False.


        Returns:
            EmbeddingResponse: The response containing the embeddings.
        """
        return await litellm.aembedding(
            input=input_text,
            caching=caching,
            dimensions=dimensions,
            model=model or self.llm_model or configs.llm.model,
            timeout=timeout or self.llm_timeout or configs.llm.timeout,
            api_key=self.llm_api_key.get_secret_value() if self.llm_api_key else configs.llm.api_key.get_secret_value(),
            api_base=self.llm_api_endpoint.unicode_string().rstrip(
                "/"
            )  # seems embedding function takes no base_url end with a slash
            if self.llm_api_endpoint
            else configs.llm.api_endpoint.unicode_string().rstrip("/"),
        )

    @overload
    async def vectorize(self, input_text: List[str], **kwargs: Unpack[EmbeddingKwargs]) -> List[List[float]]: ...
    @overload
    async def vectorize(self, input_text: str, **kwargs: Unpack[EmbeddingKwargs]) -> List[float]: ...

    async def vectorize(
        self, input_text: List[str] | str, **kwargs: Unpack[EmbeddingKwargs]
    ) -> List[List[float]] | List[float]:
        """Asynchronously generates vector embeddings for the given input text.

        Args:
            input_text (List[str] | str): A string or list of strings to generate embeddings for.
            **kwargs (Unpack[EmbeddingKwargs]): Additional keyword arguments for embedding.

        Returns:
            List[List[float]] | List[float]: The generated embeddings.
        """
        if isinstance(input_text, str):
            return (await self.aembedding([input_text], **kwargs)).data[0].get("embedding")

        return [o.get("embedding") for o in (await self.aembedding(input_text, **kwargs)).data]

    @overload
    async def pack(
        self, input_text: List[str], subject: Optional[str] = None, **kwargs: Unpack[EmbeddingKwargs]
    ) -> List[MilvusData]: ...
    @overload
    async def pack(
        self, input_text: str, subject: Optional[str] = None, **kwargs: Unpack[EmbeddingKwargs]
    ) -> MilvusData: ...

    async def pack(
        self, input_text: List[str] | str, subject: Optional[str] = None, **kwargs: Unpack[EmbeddingKwargs]
    ) -> List[MilvusData] | MilvusData:
        """Asynchronously generates MilvusData objects for the given input text.

        Args:
            input_text (List[str] | str): A string or list of strings to generate embeddings for.
            subject (Optional[str]): The subject of the input text. Defaults to None.
            **kwargs (Unpack[EmbeddingKwargs]): Additional keyword arguments for embedding.

        Returns:
            List[MilvusData] | MilvusData: The generated MilvusData objects.
        """
        if isinstance(input_text, str):
            return MilvusData(vector=await self.vectorize(input_text, **kwargs), text=input_text, subject=subject)
        vecs = await self.vectorize(input_text, **kwargs)
        return [
            MilvusData(
                vector=vec,
                text=text,
                subject=subject,
            )
            for text, vec in zip(input_text, vecs, strict=True)
        ]

    async def aquery(
        self,
        messages: List[Dict[str, str]],
        n: PositiveInt | None = None,
        **kwargs: Unpack[LLMKwargs],
    ) -> ModelResponse | CustomStreamWrapper:
        """Asynchronously queries the language model to generate a response based on the provided messages and parameters.

        Args:
            messages (List[Dict[str, str]]): A list of messages, where each message is a dictionary containing the role and content of the message.
            n (PositiveInt | None): The number of responses to generate. Defaults to the instance's `llm_generation_count` or the global configuration.
            **kwargs (Unpack[LLMKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            ModelResponse | CustomStreamWrapper: An object containing the generated response and other metadata from the model.
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
            system_message (str): The system message to provide context to the model. Defaults to an empty string.
            n (PositiveInt | None): The number of responses to generate. Defaults to the instance's `llm_generation_count` or the global configuration.
            **kwargs (Unpack[LLMKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            List[Choices | StreamingChoices]: A list of choices or streaming choices from the model response.
        """
        resp = await self.aquery(
            messages=Messages().add_system_message(system_message).add_user_message(question),
            n=n,
            **kwargs,
        )
        if isinstance(resp, ModelResponse):
            return resp.choices
        if isinstance(resp, CustomStreamWrapper):
            if configs.debug.streaming_visible:
                chunks = []
                async for chunk in resp:
                    chunks.append(chunk)
                    print(chunk.choices[0].delta.content or "", end="")  # noqa: T201
                return stream_chunk_builder(chunks).choices
            return stream_chunk_builder(await asyncstdlib.list()).choices
        logger.critical(err := f"Unexpected response type: {type(resp)}")
        raise ValueError(err)

    @overload
    async def aask(
        self,
        question: List[str],
        system_message: Optional[List[str]] = None,
        **kwargs: Unpack[LLMKwargs],
    ) -> List[str]: ...
    @overload
    async def aask(
        self,
        question: str,
        system_message: Optional[List[str]] = None,
        **kwargs: Unpack[LLMKwargs],
    ) -> List[str]: ...
    @overload
    async def aask(
        self,
        question: List[str],
        system_message: Optional[str] = None,
        **kwargs: Unpack[LLMKwargs],
    ) -> List[str]: ...

    @overload
    async def aask(
        self,
        question: str,
        system_message: Optional[str] = None,
        **kwargs: Unpack[LLMKwargs],
    ) -> str: ...

    async def aask(
        self,
        question: str | List[str],
        system_message: Optional[str | List[str]] = None,
        **kwargs: Unpack[LLMKwargs],
    ) -> str | List[str]:
        """Asynchronously asks the language model a question and returns the response content.

        Args:
            question (str | List[str]): The question to ask the model.
            system_message (str | List[str] | None): The system message to provide context to the model. Defaults to an empty string.
            **kwargs (Unpack[LLMKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            str | List[str]: The content of the model's response message.
        """
        system_message = system_message or ""
        match (isinstance(question, list), isinstance(system_message, list)):
            case (True, True):
                res = await gather(
                    *[
                        self.ainvoke(n=1, question=q, system_message=sm, **kwargs)
                        for q, sm in zip(question, system_message, strict=True)
                    ]
                )
                return [r.pop().message.content for r in res]
            case (True, False):
                res = await gather(
                    *[self.ainvoke(n=1, question=q, system_message=system_message, **kwargs) for q in question]
                )
                return [r.pop().message.content for r in res]
            case (False, True):
                res = await gather(
                    *[self.ainvoke(n=1, question=question, system_message=sm, **kwargs) for sm in system_message]
                )
                return [r.pop().message.content for r in res]
            case (False, False):
                return (
                    (
                        await self.ainvoke(
                            n=1,
                            question=question,
                            system_message=system_message,
                            **kwargs,
                        )
                    ).pop()
                ).message.content
            case _:
                raise RuntimeError("Should not reach here.")

    async def aask_validate[T](
        self,
        question: str,
        validator: Callable[[str], T | None],
        max_validations: PositiveInt = 2,
        system_message: str = "",
        **kwargs: Unpack[LLMKwargs],
    ) -> T:
        """Asynchronously asks a question and validates the response using a given validator.

        Args:
            question (str): The question to ask.
            validator (Callable[[str], T | None]): A function to validate the response.
            max_validations (PositiveInt): Maximum number of validation attempts. Defaults to 2.
            system_message (str): System message to include in the request. Defaults to an empty string.
            **kwargs (Unpack[LLMKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            T: The validated response.

        Raises:
            ValueError: If the response fails to validate after the maximum number of attempts.
        """
        for i in range(max_validations):
            if (
                response := await self.aask(
                    question=question,
                    system_message=system_message,
                    **kwargs,
                )
            ) and (validated := validator(response)):
                logger.debug(f"Successfully validated the response at {i}th attempt. response: \n{response}")
                return validated
            logger.debug(f"Failed to validate the response at {i}th attempt. response: \n{response}")
        logger.error(f"Failed to validate the response after {max_validations} attempts.")
        raise ValueError("Failed to validate the response.")

    async def aask_validate_batch[T](
        self,
        questions: List[str],
        validator: Callable[[str], T | None],
        **kwargs: Unpack[GenerateKwargs],
    ) -> List[T]:
        """Asynchronously asks a batch of questions and validates the responses using a given validator.

        Args:
            questions (List[str]): The list of questions to ask.
            validator (Callable[[str], T | None]): A function to validate the response.
            **kwargs (Unpack[GenerateKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            T: The validated response.

        Raises:
            ValueError: If the response fails to validate after the maximum number of attempts.
        """
        return await gather(*[self.aask_validate(question, validator, **kwargs) for question in questions])

    async def achoose[T: WithBriefing](
        self,
        instruction: str,
        choices: List[T],
        k: NonNegativeInt = 0,
        **kwargs: Unpack[GenerateKwargs],
    ) -> List[T]:
        """Asynchronously executes a multi-choice decision-making process, generating a prompt based on the instruction and options, and validates the returned selection results.

        Args:
            instruction (str): The user-provided instruction/question description.
            choices (List[T]): A list of candidate options, requiring elements to have `name` and `briefing` fields.
            k (NonNegativeInt): The number of choices to select, 0 means infinite. Defaults to 0.
            **kwargs (Unpack[GenerateKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            List[T]: The final validated selection result list, with element types matching the input `choices`.

        Important:
            - Uses a template engine to generate structured prompts.
            - Ensures response compliance through JSON parsing and format validation.
            - Relies on `aask_validate` to implement retry mechanisms with validation.
        """
        prompt = template_manager.render_template(
            configs.templates.make_choice_template,
            {
                "instruction": instruction,
                "options": [{"name": m.name, "briefing": m.briefing} for m in choices],
                "k": k,
            },
        )
        names = {c.name for c in choices}
        logger.debug(f"Start choosing between {names} with prompt: \n{prompt}")

        def _validate(response: str) -> List[T] | None:
            ret = JsonCapture.convert_with(response, orjson.loads)

            if not isinstance(ret, List) or (0 < k != len(ret)):
                logger.error(f"Incorrect Type or length of response: \n{ret}")
                return None
            if any(n not in names for n in ret):
                logger.error(f"Invalid choice in response: \n{ret}")
                return None

            return [next(toolbox for toolbox in choices if toolbox.name == toolbox_str) for toolbox_str in ret]

        return await self.aask_validate(
            question=prompt,
            validator=_validate,
            **kwargs,
        )

    async def apick[T: WithBriefing](
        self,
        instruction: str,
        choices: List[T],
        **kwargs: Unpack[GenerateKwargs],
    ) -> T:
        """Asynchronously picks a single choice from a list of options using AI validation.

        Args:
            instruction (str): The user-provided instruction/question description.
            choices (List[T]): A list of candidate options, requiring elements to have `name` and `briefing` fields.
            **kwargs (Unpack[GenerateKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            T: The single selected item from the choices list.

        Raises:
            ValueError: If validation fails after maximum attempts or if no valid selection is made.
        """
        return (
            await self.achoose(
                instruction=instruction,
                choices=choices,
                k=1,
                **kwargs,
            )
        )[0]

    async def ajudge(
        self,
        prompt: str,
        affirm_case: str = "",
        deny_case: str = "",
        **kwargs: Unpack[GenerateKwargs],
    ) -> bool:
        """Asynchronously judges a prompt using AI validation.

        Args:
            prompt (str): The input prompt to be judged.
            affirm_case (str): The affirmative case for the AI model. Defaults to an empty string.
            deny_case (str): The negative case for the AI model. Defaults to an empty string.
            **kwargs (Unpack[GenerateKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            bool: The judgment result (True or False) based on the AI's response.
        """

        def _validate(response: str) -> bool | None:
            ret = JsonCapture.convert_with(response, orjson.loads)
            if not isinstance(ret, bool):
                return None
            return ret

        return await self.aask_validate(
            question=template_manager.render_template(
                configs.templates.make_judgment_template,
                {"prompt": prompt, "affirm_case": affirm_case, "deny_case": deny_case},
            ),
            validator=_validate,
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

    @property
    def available_toolbox_names(self) -> List[str]:
        """Return a list of available toolbox names."""
        return [toolbox.name for toolbox in self.toolboxes]

    async def choose_toolboxes(
        self,
        task: Task,
        system_message: str = "",
        k: NonNegativeInt = 0,
        max_validations: PositiveInt = 2,
        **kwargs: Unpack[LLMKwargs],
    ) -> List[ToolBox]:
        """Asynchronously executes a multi-choice decision-making process to choose toolboxes.

        Args:
            task (Task): The task for which to choose toolboxes.
            system_message (str): Custom system-level prompt, defaults to an empty string.
            k (NonNegativeInt): The number of toolboxes to select, 0 means infinite. Defaults to 0.
            max_validations (PositiveInt): Maximum number of validation failures, default is 2.
            **kwargs (Unpack[LLMKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            List[ToolBox]: The selected toolboxes.
        """
        if not self.toolboxes:
            logger.warning("No toolboxes available.")
            return []
        return await self.achoose(
            instruction=task.briefing,  # TODO write a template to build a more robust instruction
            choices=list(self.toolboxes),
            k=k,
            max_validations=max_validations,
            system_message=system_message,
            **kwargs,
        )

    async def choose_tools(
        self,
        task: Task,
        toolbox: ToolBox,
        system_message: str = "",
        k: NonNegativeInt = 0,
        max_validations: PositiveInt = 2,
        **kwargs: Unpack[LLMKwargs],
    ) -> List[Tool]:
        """Asynchronously executes a multi-choice decision-making process to choose tools.

        Args:
            task (Task): The task for which to choose tools.
            toolbox (ToolBox): The toolbox from which to choose tools.
            system_message (str): Custom system-level prompt, defaults to an empty string.
            k (NonNegativeInt): The number of tools to select, 0 means infinite. Defaults to 0.
            max_validations (PositiveInt): Maximum number of validation failures, default is 2.
            **kwargs (Unpack[LLMKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            List[Tool]: The selected tools.
        """
        if not toolbox.tools:
            logger.warning(f"No tools available in toolbox {toolbox.name}.")
            return []
        return await self.achoose(
            instruction=task.briefing,  # TODO write a template to build a more robust instruction
            choices=toolbox.tools,
            k=k,
            max_validations=max_validations,
            system_message=system_message,
            **kwargs,
        )

    async def gather_tools_fine_grind(
        self,
        task: Task,
        box_choose_kwargs: Optional[ChooseKwargs] = None,
        tool_choose_kwargs: Optional[ChooseKwargs] = None,
    ) -> List[Tool]:
        """Asynchronously gathers tools based on the provided task and toolbox and tool selection criteria.

        Args:
            task (Task): The task for which to gather tools.
            box_choose_kwargs (Optional[ChooseKwargs]): Keyword arguments for choosing toolboxes.
            tool_choose_kwargs (Optional[ChooseKwargs]): Keyword arguments for choosing tools.

        Returns:
            List[Tool]: A list of tools gathered based on the provided task and toolbox and tool selection criteria.
        """
        box_choose_kwargs = box_choose_kwargs or {}
        tool_choose_kwargs = tool_choose_kwargs or {}

        # Choose the toolboxes
        chosen_toolboxes = await self.choose_toolboxes(task, **box_choose_kwargs)
        # Choose the tools
        chosen_tools = []
        for toolbox in chosen_toolboxes:
            chosen_tools.extend(await self.choose_tools(task, toolbox, **tool_choose_kwargs))
        return chosen_tools

    async def gather_tools(self, task: Task, **kwargs: Unpack[ChooseKwargs]) -> List[Tool]:
        """Asynchronously gathers tools based on the provided task.

        Args:
            task (Task): The task for which to gather tools.
            **kwargs (Unpack[ChooseKwargs]): Keyword arguments for choosing tools.

        Returns:
            List[Tool]: A list of tools gathered based on the provided task.
        """
        return await self.gather_tools_fine_grind(task, kwargs, kwargs)

    def supply_tools_from[S: "ToolBoxUsage"](self, others: Union[S, Iterable[S]]) -> Self:
        """Supplies tools from other ToolUsage instances to this instance.

        Args:
            others (ToolBoxUsage | Iterable[ToolBoxUsage]): A single ToolUsage instance or an iterable of ToolUsage instances
                from which to take tools.

        Returns:
            Self: The current ToolUsage instance with updated tools.
        """
        if isinstance(others, ToolBoxUsage):
            others = [others]
        for other in others:
            self.toolboxes.update(other.toolboxes)
        return self

    def provide_tools_to[S: "ToolBoxUsage"](self, others: Union[S, Iterable[S]]) -> Self:
        """Provides tools from this instance to other ToolUsage instances.

        Args:
            others (ToolBoxUsage | Iterable[ToolBoxUsage]): A single ToolUsage instance or an iterable of ToolUsage instances
                to which to provide tools.

        Returns:
            Self: The current ToolUsage instance.
        """
        if isinstance(others, ToolBoxUsage):
            others = [others]
        for other in others:
            other.toolboxes.update(self.toolboxes)
        return self
