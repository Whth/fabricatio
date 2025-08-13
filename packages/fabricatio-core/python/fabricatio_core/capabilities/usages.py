"""Module for defining LLM (Large Language Model) usage capabilities.

This module contains classes and methods to manage interactions with LLMs, including:
- Deploying models
- Querying responses
- Validating outputs
- Generating embeddings
- Selecting tools and toolboxes

It provides structured functionality for managing language model operations,
embedding generation, and tool selection workflows.
"""

import traceback
from abc import ABC
from asyncio import gather
from typing import Callable, Dict, List, Optional, Sequence, Unpack, overload

import asyncstdlib
from litellm import (
    RateLimitError,  # pyright: ignore [reportPrivateImportUsage]
    Router,  # pyright: ignore [reportPrivateImportUsage]
    stream_chunk_builder,
    token_counter,  # pyright: ignore [reportPrivateImportUsage]
)
from litellm.litellm_core_utils.streaming_handler import CustomStreamWrapper
from litellm.types.router import Deployment, LiteLLM_Params, ModelInfo
from litellm.types.utils import Choices, EmbeddingResponse, ModelResponse, StreamingChoices, TextChoices
from more_itertools import duplicates_everseen
from pydantic import NonNegativeInt, PositiveInt

from fabricatio_core import CONFIG, TEMPLATE_MANAGER, logger
from fabricatio_core.decorators import logging_exec_time
from fabricatio_core.models.generic import EmbeddingScopedConfig, LLMScopedConfig, WithBriefing
from fabricatio_core.models.kwargs_types import ChooseKwargs, EmbeddingKwargs, GenerateKwargs, LLMKwargs, ValidateKwargs
from fabricatio_core.models.llm import Messages, get_router
from fabricatio_core.utils import first_available, ok


class UseLLM(LLMScopedConfig, ABC):
    """Class that manages LLM (Large Language Model) usage parameters and methods.

    This class provides methods to deploy LLMs, query them for responses, and handle various configurations
    related to LLM usage such as API keys, endpoints, and rate limits.
    """

    def _deploy(self, deployment: Deployment) -> Router:
        """Add a deployment to the router.

        Args:
            deployment (Deployment): The deployment to be added to the router.

        Returns:
            Router: The updated router with the added deployment.
        """
        router = get_router()
        self._added_deployment = router.upsert_deployment(deployment)
        return router

    # noinspection PyTypeChecker,PydanticTypeChecker,t
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
                        kwargs.get("model") or self.llm_model or CONFIG.llm.model, "model name is not set at any place"
                    )
                ),  # pyright: ignore [reportCallIssue]
                litellm_params=(
                    p := LiteLLM_Params(
                        api_key=ok(
                            self.llm_api_key or CONFIG.llm.api_key, "llm api key is not set at any place"
                        ).get_secret_value(),
                        api_base=ok(
                            self.llm_api_endpoint or CONFIG.llm.api_endpoint,
                            "llm api endpoint is not set at any place",
                        ),
                        model=m_name,
                        tpm=self.llm_tpm or CONFIG.llm.tpm,
                        rpm=self.llm_rpm or CONFIG.llm.rpm,
                        max_retries=kwargs.get("max_retries") or self.llm_max_retries or CONFIG.llm.max_retries,
                        timeout=kwargs.get("timeout") or self.llm_timeout or CONFIG.llm.timeout,
                    )
                ),
                model_info=ModelInfo(id=hash(m_name + p.model_dump_json(exclude_none=True))),
            )
        ).acompletion(
            messages=messages,  # pyright: ignore [reportArgumentType]
            n=n or self.llm_generation_count or CONFIG.llm.generation_count,
            model=m_name,
            temperature=kwargs.get("temperature") or self.llm_temperature or CONFIG.llm.temperature,
            stop=kwargs.get("stop") or self.llm_stop_sign or CONFIG.llm.stop_sign,
            top_p=kwargs.get("top_p") or self.llm_top_p or CONFIG.llm.top_p,
            max_tokens=kwargs.get("max_tokens") or self.llm_max_tokens or CONFIG.llm.max_tokens,
            stream=first_available(
                (kwargs.get("stream"), self.llm_stream, CONFIG.llm.stream), "stream is not set at any place"
            ),
            cache={
                "no-cache": kwargs.get("no_cache"),
                "no-store": kwargs.get("no_store"),
                "cache-ttl": kwargs.get("cache_ttl"),
                "s-maxage": kwargs.get("s_maxage"),
            },
            presence_penalty=kwargs.get("presence_penalty") or self.llm_presence_penalty or CONFIG.llm.presence_penalty,
            frequency_penalty=kwargs.get("frequency_penalty")
            or self.llm_frequency_penalty
            or CONFIG.llm.frequency_penalty,
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
            Sequence[TextChoices | Choices | StreamingChoices]: A sequence of choices or streaming choices from the model response.
        """
        resp = await self.aquery(
            messages=Messages().add_system_message(system_message).add_user_message(question).as_list(),
            n=n,
            **kwargs,
        )
        if isinstance(resp, ModelResponse):
            return resp.choices
        if isinstance(resp, CustomStreamWrapper) and (pack := stream_chunk_builder(await asyncstdlib.list(resp))):
            return pack.choices
        logger.error(err := f"Unexpected response type: {type(resp)}")
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

    @logging_exec_time
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
        match (question, system_message or ""):
            case (list(q_seq), list(sm_seq)):
                res = await gather(
                    *[
                        self.ainvoke(n=1, question=q, system_message=sm, **kwargs)
                        for q, sm in zip(q_seq, sm_seq, strict=True)
                    ]
                )
                out = [r[0].message.content for r in res]  # pyright: ignore [reportAttributeAccessIssue]
            case (list(q_seq), str(sm)):
                res = await gather(*[self.ainvoke(n=1, question=q, system_message=sm, **kwargs) for q in q_seq])
                out = [r[0].message.content for r in res]  # pyright: ignore [reportAttributeAccessIssue]
            case (str(q), list(sm_seq)):
                res = await gather(*[self.ainvoke(n=1, question=q, system_message=sm, **kwargs) for sm in sm_seq])
                out = [r[0].message.content for r in res]  # pyright: ignore [reportAttributeAccessIssue]
            case (str(q), str(sm)):
                out = ((await self.ainvoke(n=1, question=q, system_message=sm, **kwargs))[0]).message.content  # pyright: ignore [reportAttributeAccessIssue]

            case _:
                raise RuntimeError("Should not reach here.")
        if out is not None:
            logger.debug(
                f"Response Token Count: {token_counter(text=out) if isinstance(out, str) else sum(token_counter(text=o) for o in out)}"
                # pyright: ignore [reportOptionalIterable]
            )
        return out  # pyright: ignore [reportReturnType]

    @overload
    async def aask_validate[T](
        self,
        question: str,
        validator: Callable[[str], T | None],
        default: T = ...,
        max_validations: PositiveInt = 2,
        **kwargs: Unpack[GenerateKwargs],
    ) -> T: ...

    @overload
    async def aask_validate[T](
        self,
        question: List[str],
        validator: Callable[[str], T | None],
        default: T = ...,
        max_validations: PositiveInt = 2,
        **kwargs: Unpack[GenerateKwargs],
    ) -> List[T]: ...

    @overload
    async def aask_validate[T](
        self,
        question: str,
        validator: Callable[[str], T | None],
        default: None = None,
        max_validations: PositiveInt = 2,
        **kwargs: Unpack[GenerateKwargs],
    ) -> Optional[T]: ...

    @overload
    async def aask_validate[T](
        self,
        question: List[str],
        validator: Callable[[str], T | None],
        default: None = None,
        max_validations: PositiveInt = 2,
        **kwargs: Unpack[GenerateKwargs],
    ) -> List[Optional[T]]: ...

    async def aask_validate[T](
        self,
        question: str | List[str],
        validator: Callable[[str], T | None],
        default: Optional[T] = None,
        max_validations: PositiveInt = 3,
        **kwargs: Unpack[GenerateKwargs],
    ) -> Optional[T] | List[Optional[T]] | List[T] | T:
        """Asynchronously asks a question and validates the response using a given validator.

        Args:
            question (str | List[str]): The question to ask.
            validator (Callable[[str], T | None]): A function to validate the response.
            default (T | None): Default value to return if validation fails. Defaults to None.
            max_validations (PositiveInt): Maximum number of validation attempts. Defaults to 3.
            **kwargs (Unpack[GenerateKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            Optional[T] | List[T | None] | List[T] | T: The validated response.
        """

        async def _inner(q: str) -> Optional[T]:
            for lap in range(max_validations):
                try:
                    if (validated := validator(response := await self.aask(question=q, **kwargs))) is not None:
                        logger.debug(f"Successfully validated the response at {lap}th attempt.")
                        return validated

                except RateLimitError as e:
                    logger.warn(f"Rate limit error:\n{e}")
                    continue
                except Exception as e:  # noqa: BLE001
                    logger.error(f"Error during validation:\n{e}")
                    logger.debug(traceback.format_exc())
                    break
                logger.error(f"Failed to validate the response at {lap}th attempt:\n{response}")
                if not kwargs.get("no_cache"):
                    kwargs["no_cache"] = True
                    logger.debug("Closed the cache for the next attempt")
            if default is None:
                logger.error(f"Failed to validate the response after {max_validations} attempts.")
            return default

        return await (gather(*[_inner(q) for q in question]) if isinstance(question, list) else _inner(question))

    async def amapping_str(
        self, requirement: str, k: NonNegativeInt = 0, **kwargs: Unpack[ValidateKwargs[Dict[str, str]]]
    ) -> Optional[Dict[str, str]]:
        """Asynchronously generates a mapping of strings based on a given requirement.

        Args:
            requirement (str): The requirement for the mapping of strings.
            k (NonNegativeInt): The number of choices to select, 0 means infinite. Defaults to 0.
            **kwargs (Unpack[ValidateKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            Optional[Dict[str, str]]: The validated response as a mapping of strings.
        """
        from fabricatio_core.parser import JsonCapture

        def _validate(resp: str) -> None | Dict[str, str]:
            if (obj := JsonCapture.validate_with(resp, target_type=dict, elements_type=str, length=k)) and all(
                isinstance(v, str) for v in obj.values()
            ):
                return obj
            return None

        return await self.aask_validate(
            TEMPLATE_MANAGER.render_template(
                CONFIG.templates.mapping_template,
                {"requirement": requirement, "k": k},
            ),
            _validate,
            **kwargs,
        )

    @overload
    async def alist_str(
        self, requirement: str, k: NonNegativeInt = 0, **kwargs: Unpack[ValidateKwargs[List[str]]]
    ) -> List[str] | None: ...

    @overload
    async def alist_str(
        self, requirement: List[str], k: NonNegativeInt = 0, **kwargs: Unpack[ValidateKwargs[List[str]]]
    ) -> List[List[str] | None] | None: ...

    async def alist_str(
        self, requirement: str | List[str], k: NonNegativeInt = 0, **kwargs: Unpack[ValidateKwargs[List[str]]]
    ) -> List[str] | List[List[str] | None] | None:
        """Asynchronously generates a list of strings based on a given requirement.

        Args:
            requirement (str): The requirement for the list of strings.
            k (NonNegativeInt): The number of choices to select, 0 means infinite. Defaults to 0.
            **kwargs (Unpack[ValidateKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            Optional[List[str]]: The validated response as a list of strings.
        """
        from fabricatio_core.parser import JsonCapture

        if isinstance(requirement, str):
            return await self.aask_validate(
                TEMPLATE_MANAGER.render_template(
                    CONFIG.templates.liststr_template,
                    {"requirement": requirement, "k": k},
                ),
                lambda resp: JsonCapture.validate_with(resp, target_type=list, elements_type=str, length=k),
                **kwargs,
            )
        if isinstance(requirement, list):
            return await self.aask_validate(
                TEMPLATE_MANAGER.render_template(
                    CONFIG.templates.liststr_template,
                    [{"requirement": r, "k": k} for r in requirement],
                ),
                lambda resp: JsonCapture.validate_with(resp, target_type=list, elements_type=str, length=k),
                **kwargs,
            )
        return None

    async def apathstr(self, requirement: str, **kwargs: Unpack[ChooseKwargs]) -> Optional[List[str]]:
        """Asynchronously generates a list of strings based on a given requirement.

        Args:
            requirement (str): The requirement for the list of strings.
            **kwargs (Unpack[ChooseKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            Optional[List[str]]: The validated response as a list of strings.
        """
        return await self.alist_str(
            TEMPLATE_MANAGER.render_template(
                CONFIG.templates.pathstr_template,
                {"requirement": requirement},
            ),
            **kwargs,
        )

    async def awhich_pathstr(self, requirement: str, **kwargs: Unpack[ValidateKwargs[List[str]]]) -> Optional[str]:
        """Asynchronously generates a single path string based on a given requirement.

        Args:
            requirement (str): The requirement for the list of strings.
            **kwargs (Unpack[ValidateKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            Optional[str]: The validated response as a single string.
        """
        if paths := await self.apathstr(
            requirement,
            k=1,
            **kwargs,
        ):
            return paths.pop()

        return None

    @overload
    async def ageneric_string(
        self,
        requirement: str,
        **kwargs: Unpack[ValidateKwargs[str]],
    ) -> Optional[str]: ...

    @overload
    async def ageneric_string(
        self,
        requirement: List[str],
        **kwargs: Unpack[ValidateKwargs[str]],
    ) -> Optional[List[Optional[str]]]: ...

    async def ageneric_string(
        self,
        requirement: str | List[str],
        **kwargs: Unpack[ValidateKwargs[str]],
    ) -> None | str | List[str | None]:
        """Asynchronously generates a generic string based on a given requirement.

        Args:
            requirement (str): The requirement for the string.
            **kwargs (Unpack[GenerateKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            Optional[str]: The generated string.
        """
        from fabricatio_core.parser import GenericCapture

        if isinstance(requirement, str):
            return await self.aask_validate(
                TEMPLATE_MANAGER.render_template(
                    CONFIG.templates.generic_string_template,
                    {"requirement": requirement, "language": GenericCapture.capture_type},
                ),
                validator=lambda resp: GenericCapture.capture(resp),
                **kwargs,
            )
        if isinstance(requirement, list):
            return await self.aask_validate(
                TEMPLATE_MANAGER.render_template(
                    CONFIG.templates.generic_string_template,
                    [{"requirement": r, "language": GenericCapture.capture_type} for r in requirement],
                ),
                validator=lambda resp: GenericCapture.capture(resp),
                **kwargs,
            )
        return None

    @overload
    async def acode_string(
        self, requirement: str, code_language: str, **kwargs: Unpack[ValidateKwargs[str]]
    ) -> Optional[str]: ...

    @overload
    async def acode_string(
        self, requirement: List[str], code_language: str, **kwargs: Unpack[ValidateKwargs[str]]
    ) -> List[Optional[str]]: ...

    async def acode_string(
        self, requirement: str | List[str], code_language: str, **kwargs: Unpack[ValidateKwargs[str]]
    ) -> None | str | List[str | None]:
        """Asynchronously generates code strings based on given requirements and code language.

        Args:
            requirement (str | List[str]): The requirement(s) for generating code strings.
            code_language (str): The programming language for the generated code.
            **kwargs (Unpack[ValidateKwargs[str]]): Additional keyword arguments for the LLM usage.

        Returns:
            None | str | List[str | None]: The generated code string(s). Returns a single string if requirement
            is a string, or a list of strings/None values if requirement is a list.
        """
        from fabricatio_core.parser import Capture

        cap = Capture.capture_code_block(code_language)

        return await self.aask_validate(
            TEMPLATE_MANAGER.render_template(
                CONFIG.templates.code_string_template,
                {"requirement": requirement, "code_language": code_language}
                if isinstance(requirement, str)
                else [{"requirement": r, "code_language": code_language} for r in requirement],
            ),
            validator=lambda resp: cap.capture(resp),
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
            Optional[List[T]]: The final validated selection result list, with element types matching the input `choices`.
        """
        from fabricatio_core.parser import JsonCapture

        if dup := list(duplicates_everseen(choices, key=lambda x: x.name)):
            logger.error(err := f"Redundant choices: {dup}")
            raise ValueError(err)
        prompt = TEMPLATE_MANAGER.render_template(
            CONFIG.templates.make_choice_template,
            {
                "instruction": instruction,
                "options": [{"name": m.name, "briefing": m.briefing} for m in choices],
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
    ) -> Optional[bool]:
        """Asynchronously judges a prompt using AI validation.

        Args:
            prompt (str): The input prompt to be judged.
            affirm_case (str): The affirmative case for the AI model. Defaults to an empty string.
            deny_case (str): The negative case for the AI model. Defaults to an empty string.
            **kwargs (Unpack[ValidateKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            bool: The judgment result (True or False) based on the AI's response.
        """
        from fabricatio_core.parser import JsonCapture

        return await self.aask_validate(
            question=TEMPLATE_MANAGER.render_template(
                CONFIG.templates.make_judgment_template,
                {"prompt": prompt, "affirm_case": affirm_case, "deny_case": deny_case},
            ),
            validator=lambda resp: JsonCapture.validate_with(resp, target_type=bool),
            **kwargs,
        )


class UseEmbedding(UseLLM, EmbeddingScopedConfig, ABC):
    """A class representing the embedding model.

    This class extends LLMUsage and provides methods to generate embeddings for input text using various models.
    """

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
        max_len = self.embedding_max_sequence_length or CONFIG.embedding.max_sequence_length
        if max_len and any(length := (token_counter(text=t)) > max_len for t in input_text):
            logger.error(err := f"Input text exceeds maximum sequence length {max_len}, got {length}.")
            raise ValueError(err)

        return await get_router().aembedding(
            input=input_text,
            caching=caching or self.embedding_caching or CONFIG.embedding.caching,
            dimensions=dimensions or self.embedding_dimensions or CONFIG.embedding.dimensions,
            model=ok(model or self.embedding_model or CONFIG.embedding.model, "Embedding model not set at any level!"),
            timeout=timeout
            or self.embedding_timeout
            or CONFIG.embedding.timeout
            or self.llm_timeout
            or CONFIG.llm.timeout,
            api_key=ok(
                self.embedding_api_key or CONFIG.embedding.api_key or self.llm_api_key or CONFIG.llm.api_key
            ).get_secret_value(),
            api_base=ok(
                self.embedding_api_endpoint
                or CONFIG.embedding.api_endpoint
                or self.llm_api_endpoint
                or CONFIG.llm.api_endpoint
            ).rstrip("/"),
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
