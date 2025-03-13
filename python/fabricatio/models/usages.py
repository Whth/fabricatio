"""This module contains classes that manage the usage of language models and tools in tasks."""

from asyncio import gather
from typing import Callable, Dict, Iterable, List, Optional, Self, Sequence, Set, Type, Union, Unpack, overload

import asyncstdlib
import litellm
from fabricatio._rust_instances import TEMPLATE_MANAGER
from fabricatio.config import configs
from fabricatio.journal import logger
from fabricatio.models.generic import ScopedConfig, WithBriefing
from fabricatio.models.kwargs_types import ChooseKwargs, EmbeddingKwargs, GenerateKwargs, LLMKwargs, ValidateKwargs
from fabricatio.models.task import Task
from fabricatio.models.tool import Tool, ToolBox
from fabricatio.models.utils import Messages, ok
from fabricatio.parser import GenericCapture, JsonCapture
from litellm import Router, stream_chunk_builder  # pyright: ignore [reportPrivateImportUsage]
from litellm.types.router import Deployment, LiteLLM_Params, ModelInfo
from litellm.types.utils import (
    Choices,
    EmbeddingResponse,
    ModelResponse,
    StreamingChoices,
    TextChoices,
)
from litellm.utils import CustomStreamWrapper  # pyright: ignore [reportPrivateImportUsage]
from more_itertools import duplicates_everseen
from pydantic import Field, NonNegativeInt, PositiveInt

if configs.cache.enabled and configs.cache.type:
    litellm.enable_cache(type=configs.cache.type, **configs.cache.params)
    logger.success(f"{configs.cache.type.name} Cache enabled")

ROUTER = Router(
    routing_strategy="usage-based-routing-v2",
    allowed_fails=configs.routing.allowed_fails,
    retry_after=configs.routing.retry_after,
    cooldown_time=configs.routing.cooldown_time,
)


class LLMUsage(ScopedConfig):
    """Class that manages LLM (Large Language Model) usage parameters and methods."""

    def _deploy(self, deployment: Deployment) -> Router:
        """Add a deployment to the router."""
        self._added_deployment = ROUTER.upsert_deployment(deployment)
        return ROUTER

    @classmethod
    def _scoped_model(cls) -> Type["LLMUsage"]:
        return LLMUsage

    # noinspection PyTypeChecker,PydanticTypeChecker
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
        # noinspection PyTypeChecker,PydanticTypeChecker
        return await self._deploy(
            Deployment(
                model_name=(
                    m_name := ok(
                        kwargs.get("model") or self.llm_model or configs.llm.model, "model name is not set at any place"
                    )
                ),  # pyright: ignore [reportCallIssue]
                litellm_params=(
                    p := LiteLLM_Params(
                        api_key=ok(
                            self.llm_api_key or configs.llm.api_key, "llm api key is not set at any place"
                        ).get_secret_value(),
                        api_base=ok(
                            self.llm_api_endpoint or configs.llm.api_endpoint,
                            "llm api endpoint is not set at any place",
                        ).unicode_string(),
                        model=m_name,
                        tpm=self.llm_tpm or configs.llm.tpm,
                        rpm=self.llm_rpm or configs.llm.rpm,
                        max_retries=kwargs.get("max_retries") or self.llm_max_retries or configs.llm.max_retries,
                        timeout=kwargs.get("timeout") or self.llm_timeout or configs.llm.timeout,
                    )
                ),
                model_info=ModelInfo(id=hash(m_name + p.model_dump_json(exclude_none=True))),
            )
        ).acompletion(
            messages=messages,  # pyright: ignore [reportArgumentType]
            n=n or self.llm_generation_count or configs.llm.generation_count,
            model=m_name,
            temperature=kwargs.get("temperature") or self.llm_temperature or configs.llm.temperature,
            stop=kwargs.get("stop") or self.llm_stop_sign or configs.llm.stop_sign,
            top_p=kwargs.get("top_p") or self.llm_top_p or configs.llm.top_p,
            max_tokens=kwargs.get("max_tokens") or self.llm_max_tokens or configs.llm.max_tokens,
            stream=ok(kwargs.get("stream") or self.llm_stream or configs.llm.stream, "stream is not set at any place"),
            cache={
                "no-cache": kwargs.get("no_cache"),
                "no-store": kwargs.get("no_store"),
                "cache-ttl": kwargs.get("cache_ttl"),
                "s-maxage": kwargs.get("s_maxage"),
            },
        )

    async def ainvoke(
        self,
        question: str,
        system_message: str = "",
        n: PositiveInt | None = None,
        **kwargs: Unpack[LLMKwargs],
    ) -> Sequence[TextChoices | Choices | StreamingChoices]:
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
            if not configs.debug.streaming_visible and (pack := stream_chunk_builder(await asyncstdlib.list())):
                return pack.choices
            chunks = []
            async for chunk in resp:
                chunks.append(chunk)
                print(chunk.choices[0].delta.content or "", end="")  # noqa: T201
            if pack := stream_chunk_builder(chunks):
                return pack.choices
        logger.critical(err := f"Unexpected response type: {type(resp)}")
        raise ValueError(err)

    @overload
    async def aask(
        self,
        question: List[str],
        system_message: List[str],
        **kwargs: Unpack[LLMKwargs],
    ) -> List[str]: ...
    @overload
    async def aask(
        self,
        question: str,
        system_message: List[str],
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
        match (question, system_message):
            case (list(q_seq), list(sm_seq)):
                res = await gather(
                    *[
                        self.ainvoke(n=1, question=q, system_message=sm, **kwargs)
                        for q, sm in zip(q_seq, sm_seq, strict=True)
                    ]
                )
                return [r[0].message.content for r in res]  # pyright: ignore [reportReturnType, reportAttributeAccessIssue]
            case (list(q_seq), str(sm)):
                res = await gather(*[self.ainvoke(n=1, question=q, system_message=sm, **kwargs) for q in q_seq])
                return [r[0].message.content for r in res]  # pyright: ignore [reportReturnType, reportAttributeAccessIssue]
            case (str(q), list(sm_seq)):
                res = await gather(*[self.ainvoke(n=1, question=q, system_message=sm, **kwargs) for sm in sm_seq])
                return [r[0].message.content for r in res]  # pyright: ignore [reportReturnType, reportAttributeAccessIssue]
            case (str(q), str(sm)):
                return ((await self.ainvoke(n=1, question=q, system_message=sm, **kwargs))[0]).message.content  # pyright: ignore [reportReturnType, reportAttributeAccessIssue]
            case _:
                raise RuntimeError("Should not reach here.")

    @overload
    async def aask_validate[T](
        self,
        question: str,
        validator: Callable[[str], T | None],
        default: T = ...,
        max_validations: PositiveInt = 2,
        co_extractor: Optional[GenerateKwargs] = None,
        **kwargs: Unpack[GenerateKwargs],
    ) -> T: ...
    @overload
    async def aask_validate[T](
        self,
        question: List[str],
        validator: Callable[[str], T | None],
        default: T = ...,
        max_validations: PositiveInt = 2,
        co_extractor: Optional[GenerateKwargs] = None,
        **kwargs: Unpack[GenerateKwargs],
    ) -> List[T]: ...
    @overload
    async def aask_validate[T](
        self,
        question: str,
        validator: Callable[[str], T | None],
        default: None = None,
        max_validations: PositiveInt = 2,
        co_extractor: Optional[GenerateKwargs] = None,
        **kwargs: Unpack[GenerateKwargs],
    ) -> Optional[T]: ...

    @overload
    async def aask_validate[T](
        self,
        question: List[str],
        validator: Callable[[str], T | None],
        default: None = None,
        max_validations: PositiveInt = 2,
        co_extractor: Optional[GenerateKwargs] = None,
        **kwargs: Unpack[GenerateKwargs],
    ) -> List[Optional[T]]: ...

    async def aask_validate[T](
        self,
        question: str | List[str],
        validator: Callable[[str], T | None],
        default: Optional[T] = None,
        max_validations: PositiveInt = 2,
        co_extractor: Optional[GenerateKwargs] = None,
        **kwargs: Unpack[GenerateKwargs],
    ) -> Optional[T] | List[Optional[T]] | List[T] | T:
        """Asynchronously asks a question and validates the response using a given validator.

        Args:
            question (str): The question to ask.
            validator (Callable[[str], T | None]): A function to validate the response.
            default (T | None): Default value to return if validation fails. Defaults to None.
            max_validations (PositiveInt): Maximum number of validation attempts. Defaults to 2.
            co_extractor (Optional[GenerateKwargs]): Keyword arguments for the co-extractor, if provided will enable co-extraction.
            **kwargs (Unpack[LLMKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            T: The validated response.

        """

        async def _inner(q: str) -> Optional[T]:
            for lap in range(max_validations):
                try:
                    if (response := await self.aask(question=q, **kwargs)) and (validated := validator(response)):
                        logger.debug(f"Successfully validated the response at {lap}th attempt.")
                        return validated

                    if co_extractor and (
                        (
                            co_response := await self.aask(
                                question=(
                                    TEMPLATE_MANAGER.render_template(
                                        configs.templates.co_validation_template,
                                        {"original_q": q, "original_a": response},
                                    )
                                ),
                                **co_extractor,
                            )
                        )
                        and (validated := validator(co_response))
                    ):
                        logger.debug(f"Successfully validated the co-response at {lap}th attempt.")
                        return validated
                except Exception as e:  # noqa: BLE001
                    logger.error(f"Error during validation: \n{e}")
                    break
                if not kwargs.get("no_cache"):
                    kwargs["no_cache"] = True
                    logger.debug("Closed the cache for the next attempt")
            if default is None:
                logger.error(f"Failed to validate the response after {max_validations} attempts.")
            return default

        if isinstance(question, str):
            return await _inner(question)

        return await gather(*[_inner(q) for q in question])

    async def aliststr(
        self, requirement: str, k: NonNegativeInt = 0, **kwargs: Unpack[ValidateKwargs[List[str]]]
    ) -> Optional[List[str]]:
        """Asynchronously generates a list of strings based on a given requirement.

        Args:
            requirement (str): The requirement for the list of strings.
            k (NonNegativeInt): The number of choices to select, 0 means infinite. Defaults to 0.
            **kwargs (Unpack[ValidateKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            List[str]: The validated response as a list of strings.
        """
        return await self.aask_validate(
            TEMPLATE_MANAGER.render_template(
                configs.templates.liststr_template,
                {"requirement": requirement, "k": k},
            ),
            lambda resp: JsonCapture.validate_with(resp, target_type=list, elements_type=str, length=k),
            **kwargs,
        )

    async def apathstr(self, requirement: str, **kwargs: Unpack[ChooseKwargs[List[str]]]) -> Optional[List[str]]:
        """Asynchronously generates a list of strings based on a given requirement.

        Args:
            requirement (str): The requirement for the list of strings.
            **kwargs (Unpack[ChooseKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            List[str]: The validated response as a list of strings.
        """
        return await self.aliststr(
            TEMPLATE_MANAGER.render_template(
                configs.templates.pathstr_template,
                {"requirement": requirement},
            ),
            **kwargs,
        )

    async def awhich_pathstr(self, requirement: str, **kwargs: Unpack[ValidateKwargs[List[str]]]) -> str:
        """Asynchronously generates a single path string based on a given requirement.

        Args:
            requirement (str): The requirement for the list of strings.
            **kwargs (Unpack[ValidateKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            str: The validated response as a single string.
        """
        return ok(
            await self.apathstr(
                requirement,
                k=1,
                **kwargs,
            )
        ).pop()

    async def ageneric_string(self, requirement: str, **kwargs: Unpack[ValidateKwargs[str]]) -> Optional[str]:
        """Asynchronously generates a generic string based on a given requirement.

        Args:
            requirement (str): The requirement for the string.
            **kwargs (Unpack[GenerateKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            str: The generated string.
        """
        return await self.aask_validate(  # pyright: ignore [reportReturnType]
            TEMPLATE_MANAGER.render_template(
                configs.templates.generic_string_template,
                {"requirement": requirement, "language": GenericCapture.capture_type},
            ),
            validator=lambda resp: GenericCapture.capture(resp),
            **kwargs,
        )

    async def achoose[T: WithBriefing](
        self,
        instruction: str,
        choices: List[T],
        k: NonNegativeInt = 0,
        **kwargs: Unpack[ValidateKwargs[List[T]]],
    ) -> Optional[List[T]]:
        """Asynchronously executes a multi-choice decision-making process, generating a prompt based on the instruction and options, and validates the returned selection results.

        Args:
            instruction (str): The user-provided instruction/question description.
            choices (List[T]): A list of candidate options, requiring elements to have `name` and `briefing` fields.
            k (NonNegativeInt): The number of choices to select, 0 means infinite. Defaults to 0.
            **kwargs (Unpack[ValidateKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            List[T]: The final validated selection result list, with element types matching the input `choices`.

        Important:
            - Uses a template engine to generate structured prompts.
            - Ensures response compliance through JSON parsing and format validation.
            - Relies on `aask_validate` to implement retry mechanisms with validation.
        """
        if dup := duplicates_everseen(choices, key=lambda x: x.name):
            logger.error(err := f"Redundant choices: {dup}")
            raise ValueError(err)
        prompt = TEMPLATE_MANAGER.render_template(
            configs.templates.make_choice_template,
            {
                "instruction": instruction,
                "options": [m.model_dump(include={"name", "briefing"}) for m in choices],
                "k": k,
            },
        )
        names = {c.name for c in choices}

        logger.debug(f"Start choosing between {names} with prompt: \n{prompt}")

        def _validate(response: str) -> List[T] | None:
            ret = JsonCapture.validate_with(response, target_type=List, elements_type=str, length=k)
            if ret is None or set(ret) - names:
                return None
            return [
                next(candidate for candidate in choices if candidate.name == candidate_name) for candidate_name in ret
            ]

        return await self.aask_validate(
            question=prompt,
            validator=_validate,
            **kwargs,
        )

    async def apick[T: WithBriefing](
        self,
        instruction: str,
        choices: List[T],
        **kwargs: Unpack[ValidateKwargs[List[T]]],
    ) -> T:
        """Asynchronously picks a single choice from a list of options using AI validation.

        Args:
            instruction (str): The user-provided instruction/question description.
            choices (List[T]): A list of candidate options, requiring elements to have `name` and `briefing` fields.
            **kwargs (Unpack[ValidateKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            T: The single selected item from the choices list.

        Raises:
            ValueError: If validation fails after maximum attempts or if no valid selection is made.
        """
        return ok(
            await self.achoose(
                instruction=instruction,
                choices=choices,
                k=1,
                **kwargs,
            ),
        )[0]

    async def ajudge(
        self,
        prompt: str,
        affirm_case: str = "",
        deny_case: str = "",
        **kwargs: Unpack[ValidateKwargs[bool]],
    ) -> bool:
        """Asynchronously judges a prompt using AI validation.

        Args:
            prompt (str): The input prompt to be judged.
            affirm_case (str): The affirmative case for the AI model. Defaults to an empty string.
            deny_case (str): The negative case for the AI model. Defaults to an empty string.
            **kwargs (Unpack[ValidateKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            bool: The judgment result (True or False) based on the AI's response.
        """
        return await self.aask_validate(
            question=TEMPLATE_MANAGER.render_template(
                configs.templates.make_judgment_template,
                {"prompt": prompt, "affirm_case": affirm_case, "deny_case": deny_case},
            ),
            validator=lambda resp: JsonCapture.validate_with(resp, target_type=bool),
            **kwargs,
        )


class EmbeddingUsage(LLMUsage):
    """A class representing the embedding model."""

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
            dimensions (Optional[int]): The dimensions of the embedding output should have, which is used to validate the result. Defaults to None.
            timeout (Optional[PositiveInt]): The timeout for the embedding request. Defaults to the instance's `llm_timeout` or the global configuration.
            caching (Optional[bool]): Whether to cache the embedding result. Defaults to False.


        Returns:
            EmbeddingResponse: The response containing the embeddings.
        """
        # check seq length
        max_len = self.embedding_max_sequence_length or configs.embedding.max_sequence_length
        if max_len and any(len(t) > max_len for t in input_text):
            logger.error(err := f"Input text exceeds maximum sequence length {max_len}.")
            raise ValueError(err)

        return await litellm.aembedding(
            input=input_text,
            caching=caching or self.embedding_caching or configs.embedding.caching,
            dimensions=dimensions or self.embedding_dimensions or configs.embedding.dimensions,
            model=model or self.embedding_model or configs.embedding.model or self.llm_model or configs.llm.model,
            timeout=timeout
            or self.embedding_timeout
            or configs.embedding.timeout
            or self.llm_timeout
            or configs.llm.timeout,
            api_key=ok(
                self.embedding_api_key or configs.embedding.api_key or self.llm_api_key or configs.llm.api_key
            ).get_secret_value(),
            api_base=ok(
                self.embedding_api_endpoint
                or configs.embedding.api_endpoint
                or self.llm_api_endpoint
                or configs.llm.api_endpoint
            )
            .unicode_string()
            .rstrip("/"),
            # seems embedding function takes no base_url end with a slash
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
        **kwargs: Unpack[ChooseKwargs[List[ToolBox]]],
    ) -> Optional[List[ToolBox]]:
        """Asynchronously executes a multi-choice decision-making process to choose toolboxes.

        Args:
            task (Task): The task for which to choose toolboxes.
            system_message (str): Custom system-level prompt, defaults to an empty string.
            **kwargs (Unpack[LLMKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            List[ToolBox]: The selected toolboxes.
        """
        if not self.toolboxes:
            logger.warning("No toolboxes available.")
            return []
        return await self.achoose(
            instruction=task.briefing,
            choices=list(self.toolboxes),
            **kwargs,
        )

    async def choose_tools(
        self,
        task: Task,
        toolbox: ToolBox,
        **kwargs: Unpack[ChooseKwargs[List[Tool]]],
    ) -> Optional[List[Tool]]:
        """Asynchronously executes a multi-choice decision-making process to choose tools.

        Args:
            task (Task): The task for which to choose tools.
            toolbox (ToolBox): The toolbox from which to choose tools.
            **kwargs (Unpack[LLMKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            List[Tool]: The selected tools.
        """
        if not toolbox.tools:
            logger.warning(f"No tools available in toolbox {toolbox.name}.")
            return []
        return await self.achoose(
            instruction=task.briefing,
            choices=toolbox.tools,
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
        chosen_toolboxes = ok(await self.choose_toolboxes(task, **box_choose_kwargs))
        # Choose the tools
        chosen_tools = []
        for toolbox in chosen_toolboxes:
            chosen_tools.extend(ok(await self.choose_tools(task, toolbox, **tool_choose_kwargs)))
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
