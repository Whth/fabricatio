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
from enum import IntEnum, StrEnum
from typing import Callable, Dict, List, Optional, Set, Tuple, Type, Unpack, cast, overload

from more_itertools import duplicates_everseen
from pydantic import NonNegativeInt, PositiveInt, ValidationError

from fabricatio_core import rust
from fabricatio_core.decorators import logging_exec_time
from fabricatio_core.models.generic import EmbeddingScopedConfig, LLMScopedConfig, RerankerScopedConfig, WithBriefing
from fabricatio_core.models.kwargs_types import (
    ChooseKwargs,
    EmbeddingKwargs,
    LLMKwargs,
    RerankerKwargs,
    ValidateKwargs,
)
from fabricatio_core.rust import CONFIG, TEMPLATE_MANAGER, CodeSnippet, logger
from fabricatio_core.utils import ok, override_kwargs


class UseLLM(LLMScopedConfig, ABC):
    """Class that manages LLM (Large Language Model) usage parameters and methods.

    This class provides methods to deploy LLMs, query them for responses, and handle various configurations
    related to LLM usage such as API keys, endpoints, and rate limits.
    """

    @overload
    async def aask(
        self,
        question: List[str],
        send_to: Optional[str] = None,
        **kwargs: Unpack[LLMKwargs],
    ) -> List[str]: ...

    @overload
    async def aask(
        self,
        question: str,
        send_to: Optional[str] = None,
        **kwargs: Unpack[LLMKwargs],
    ) -> str: ...

    @logging_exec_time
    async def aask(
        self,
        question: str | List[str],
        send_to: Optional[str] = None,
        **kwargs: Unpack[LLMKwargs],
    ) -> str | List[str]:
        """Asynchronously asks the language model a question and returns the response content.

        Args:
            question (str | List[str]): The question or list of questions to ask the model.
            send_to: the completion model group to use
            **kwargs (Unpack[LLMKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            str | List[str]: The content of the model's response message. Returns a single string if input is a string,
                or a list of strings if input is a list of strings.
        """
        kw = self._resolve_completion_params(**kwargs)
        resolved_send_to = self._resolve_completion_send_to(send_to=send_to)
        return await rust.router_usage.ask(question=question, send_to=resolved_send_to, **kw)

    @overload
    async def aask_validate[T](
        self,
        question: str,
        validator: Callable[[str], T | None],
        default: T = ...,
        max_validations: PositiveInt = 3,
        send_to: Optional[str] = None,
        **kwargs: Unpack[LLMKwargs],
    ) -> T: ...

    @overload
    async def aask_validate[T](
        self,
        question: List[str],
        validator: Callable[[str], T | None],
        default: T = ...,
        max_validations: PositiveInt = 3,
        send_to: Optional[str] = None,
        **kwargs: Unpack[LLMKwargs],
    ) -> List[T]: ...

    @overload
    async def aask_validate[T](
        self,
        question: str,
        validator: Callable[[str], T | None],
        default: None = None,
        max_validations: PositiveInt = 3,
        send_to: Optional[str] = None,
        **kwargs: Unpack[LLMKwargs],
    ) -> Optional[T]: ...

    @overload
    async def aask_validate[T](
        self,
        question: List[str],
        validator: Callable[[str], T | None],
        default: None = None,
        max_validations: PositiveInt = 3,
        send_to: Optional[str] = None,
        **kwargs: Unpack[LLMKwargs],
    ) -> List[Optional[T]]: ...

    @overload
    async def aask_validate[T](
        self,
        question: str | List[str],
        validator: Callable[[str], T | None],
        default: Optional[T] = None,
        max_validations: PositiveInt = 3,
        send_to: Optional[str] = None,
        **kwargs: Unpack[LLMKwargs],
    ) -> None | T | List[Optional[T]] | List[T]: ...

    async def aask_validate[T](
        self,
        question: str | List[str],
        validator: Callable[[str], T | None],
        default: Optional[T] = None,
        max_validations: PositiveInt = 3,
        send_to: Optional[str] = None,
        **kwargs: Unpack[LLMKwargs],
    ) -> None | T | List[Optional[T]] | List[T]:
        """Asynchronously asks a question and validates the response using a given validator.

        Args:
            question (str | List[str]): The question to ask.
            validator (Callable[[str], T | None]): A function to validate the response.
            default (T | None): Default value to return if validation fails. Defaults to None.
            max_validations (PositiveInt): Maximum number of validation attempts. Defaults to 3.
            send_to: the completion model group to use
            **kwargs (Unpack[LLMKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            Optional[T] | List[T | None] | List[T] | T: The validated response.
        """

        async def _inner(q: str) -> Optional[T]:
            _kw = kwargs
            for lap in range(max_validations):
                try:
                    if (
                        validated := validator(response := await self.aask(question=q, send_to=send_to, **_kw))
                    ) is not None:
                        logger.debug(f"Successfully validated the response at {lap}th attempt.")
                        return validated
                except ValidationError as e:
                    logger.error(f"Error during validation:\n{e}")
                    logger.debug(traceback.format_exc())
                logger.error(f"Failed to validate the response at {lap}th attempt:\n{response}")
                _kw = override_kwargs(_kw, no_cache=True)

            if default is None:
                logger.error(f"Failed to validate the response after {max_validations} attempts.")
            return default

        return await (gather(*[_inner(q) for q in question]) if isinstance(question, list) else _inner(question))

    @overload
    async def amapping_kv[K: int | str | bool, V: int | float | str | bool](
        self,
        requirement: str,
        key_type: Type[K],
        value_type: Type[V],
        k: NonNegativeInt = 0,
        send_to: Optional[str] = None,
        **kwargs: Unpack[ValidateKwargs[Dict[K, V]]],
    ) -> Optional[Dict[K, V]]: ...

    @overload
    async def amapping_kv[K: int | str | bool, V: int | float | str | bool](
        self,
        requirement: List[str],
        key_type: Type[K],
        value_type: Type[V],
        k: NonNegativeInt = 0,
        send_to: Optional[str] = None,
        **kwargs: Unpack[ValidateKwargs[Dict[K, V]]],
    ) -> List[Optional[Dict[K, V]]] | None: ...

    async def amapping_kv[K: int | str | bool, V: int | float | str | bool](
        self,
        requirement: str | List[str],
        key_type: Type[K],
        value_type: Type[V],
        k: NonNegativeInt = 0,
        send_to: Optional[str] = None,
        **kwargs: Unpack[ValidateKwargs[Dict[K, V]]],
    ) -> None | Dict[K, V] | List[Optional[Dict[K, V]]]:
        """Asynchronously maps a requirement to a key-value dictionary via LLM.

        Supports arbitrary key/value types through `key_type` and `value_type` parameters.

        Args:
            requirement: A single string or list of strings describing the mapping task.
            key_type: The type of the keys in the mapping (String or Int).
            value_type: The type of the values in the mapping (String, Int, or Float).
            k: The number of key-value pairs to generate, 0 means infinite. Defaults to 0.
            send_to: the completion model group to use
            **kwargs: Additional keyword arguments for LLM configuration and validation.

        Returns:
            Optional[Dict] for single requirement, List[Optional[Dict]] for batch.
        """
        params = self._resolve_mapping_kv_params(key_type=key_type, value_type=value_type, **kwargs)
        resolved_send_to = self._resolve_completion_send_to(send_to=send_to)

        return await rust.router_usage.mapping_kv(
            requirement=requirement,
            k=k,
            send_to=resolved_send_to,
            **params,
        )

    @overload
    async def alist_v[T: int | str | bool | float](
        self,
        requirement: str,
        value_type: Type[T],
        k: NonNegativeInt = 0,
        send_to: Optional[str] = None,
        **kwargs: Unpack[ValidateKwargs[List[T]]],
    ) -> List[T] | None: ...

    @overload
    async def alist_v[T: int | str | bool | float](
        self,
        requirement: List[str],
        value_type: Type[T],
        k: NonNegativeInt = 0,
        send_to: Optional[str] = None,
        **kwargs: Unpack[ValidateKwargs[List[T]]],
    ) -> List[List[T] | None] | None: ...

    async def alist_v[T: int | str | bool | float](
        self,
        requirement: str | List[str],
        value_type: Type[T],
        k: NonNegativeInt = 0,
        send_to: Optional[str] = None,
        **kwargs: Unpack[ValidateKwargs[List[T]]],
    ) -> List[T] | List[List[T] | None] | None:
        """Asynchronously generates a list of values based on a given requirement.

        Args:
            requirement (str | List[str]): The requirement for the list.
            value_type (Type[T]): The type of list elements (str, int, float, bool). Defaults to str.
            k (NonNegativeInt): The number of choices to select, 0 means infinite. Defaults to 0.
            send_to (Optional[str]): The group name of which the requests will be sent.
            **kwargs (Unpack[ValidateKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            List[T] | List[List[T] | None] | None: The validated response as a list of values.
        """
        params = self._resolve_listing_v_params(value_type=value_type, **kwargs)
        resolved_send_to = self._resolve_completion_send_to(send_to=send_to)
        return await rust.router_usage.listing_v(requirement=requirement, k=k, send_to=resolved_send_to, **params)

    async def apathstr(
        self,
        requirement: str,
        send_to: Optional[str] = None,
        **kwargs: Unpack[ChooseKwargs[str]],
    ) -> Optional[List[str]]:
        """Asynchronously generates a list of path strings based on a given requirement.

        Args:
            requirement (str): The requirement for the list of paths.
            send_to (Optional[str]): The group name of which the requests will be sent.
            **kwargs (Unpack[ChooseKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            Optional[List[str]]: The validated response as a list of path strings.
        """
        return await self.alist_v(
            TEMPLATE_MANAGER.render_template(
                CONFIG.templates.pathstr_template,
                {"requirement": requirement},
            ),
            value_type=str,
            send_to=send_to,
            **kwargs,
        )

    async def awhich_pathstr(
        self,
        requirement: str,
        send_to: Optional[str] = None,
        **kwargs: Unpack[ValidateKwargs[List[str]]],
    ) -> Optional[str]:
        """Asynchronously generates a single path string based on a given requirement.

        Args:
            requirement (str): The requirement for the path.
            send_to (Optional[str]): The group name of which the requests will be sent.
            **kwargs (Unpack[ValidateKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            Optional[str]: The validated response as a single string.
        """
        if paths := await self.apathstr(
            requirement,
            k=1,
            send_to=send_to,
            **kwargs,
        ):
            return paths.pop()

        return None

    @overload
    async def ageneric_string(
        self,
        requirement: str,
        send_to: Optional[str] = None,
        **kwargs: Unpack[ValidateKwargs[str]],
    ) -> Optional[str]: ...

    @overload
    async def ageneric_string(
        self,
        requirement: List[str],
        send_to: Optional[str] = None,
        **kwargs: Unpack[ValidateKwargs[str]],
    ) -> Optional[List[Optional[str]]]: ...

    async def ageneric_string(
        self,
        requirement: str | List[str],
        send_to: Optional[str] = None,
        **kwargs: Unpack[ValidateKwargs[str]],
    ) -> None | str | List[str | None]:
        """Asynchronously generates a generic string based on a given requirement.

        Args:
            requirement (str): The requirement for the string.
            send_to (Optional[str]): The group name of which the requests will be sent.
            **kwargs (Unpack[LLMKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            Optional[str]: The generated string.
        """
        params = self._resolve_validation_params(**kwargs)
        resolved_send_to = self._resolve_completion_send_to(send_to=send_to)
        return await rust.router_usage.generic_string(requirement=requirement, send_to=resolved_send_to, **params)

    @overload
    async def acode_string(
        self,
        requirement: str,
        code_language: Optional[str] = None,
        send_to: Optional[str] = None,
        **kwargs: Unpack[ValidateKwargs[str]],
    ) -> Optional[str]: ...

    @overload
    async def acode_string(
        self,
        requirement: List[str],
        code_language: Optional[str] = None,
        send_to: Optional[str] = None,
        **kwargs: Unpack[ValidateKwargs[str]],
    ) -> List[Optional[str]]: ...

    async def acode_string(
        self,
        requirement: str | List[str],
        code_language: Optional[str] = None,
        send_to: Optional[str] = None,
        **kwargs: Unpack[ValidateKwargs[str]],
    ) -> None | str | List[str | None]:
        """Asynchronously generates code strings based on given requirements and code language.

        Args:
            requirement (str | List[str]): The requirement(s) for generating code strings.
            code_language (str): The programming language for the generated code.
            send_to (Optional[str]): The group name of which the requests will be sent.
            **kwargs (Unpack[ValidateKwargs[str]]): Additional keyword arguments for the LLM usage.

        Returns:
            None | str | List[str | None]: The generated code string(s). Returns a single string if requirement
            is a string, or a list of strings/None values if requirement is a list.
        """
        params = self._resolve_validation_params(**kwargs)
        resolved_send_to = self._resolve_completion_send_to(send_to=send_to)
        return await rust.router_usage.code_string(
            requirement=requirement,
            code_language=code_language,
            send_to=resolved_send_to,
            **params,
        )

    @overload
    async def acode_snippets(
        self,
        requirement: str,
        code_language: Optional[str] = None,
        send_to: Optional[str] = None,
        **kwargs: Unpack[ValidateKwargs[List[CodeSnippet]]],
    ) -> Optional[List[CodeSnippet]]: ...

    @overload
    async def acode_snippets(
        self,
        requirement: List[str],
        code_language: Optional[str] = None,
        send_to: Optional[str] = None,
        **kwargs: Unpack[ValidateKwargs[List[CodeSnippet]]],
    ) -> List[List[CodeSnippet] | None] | None: ...

    async def acode_snippets(
        self,
        requirement: str | List[str],
        code_language: Optional[str] = None,
        send_to: Optional[str] = None,
        **kwargs: Unpack[ValidateKwargs[List[CodeSnippet]]],
    ) -> None | List[CodeSnippet] | List[List[CodeSnippet] | None]:
        """Asynchronously generates code snippets based on given requirements and code language.

        Args:
            requirement (str | List[str]): The requirement(s) for generating code snippets.
            code_language (Optional[str]): The programming language for the generated code. Defaults to None.
            send_to (Optional[str]): The group name of which the requests will be sent.
            **kwargs (Unpack[ValidateKwargs[List[CodeSnippet]]]): Additional keyword arguments for the LLM usage.

        Returns:
            None | List[CodeSnippet] | List[List[CodeSnippet] | None]: The generated code snippet(s).
            Returns a list of CodeSnippet objects if requirement is a string, or a list of lists of
            CodeSnippet objects or None if requirement is a list.
        """
        params = self._resolve_validation_params(**kwargs)
        resolved_send_to = self._resolve_completion_send_to(send_to=send_to)
        return await rust.router_usage.code_snippets(
            requirement=requirement,
            code_language=code_language,
            send_to=resolved_send_to,
            **params,
        )

    async def achoose[T: WithBriefing](
        self,
        instruction: str,
        choices: List[T],
        k: NonNegativeInt = 0,
        is_included_fn: Optional[Callable[[Set[str], T], bool]] = None,
        send_to: Optional[str] = None,
        **kwargs: Unpack[ValidateKwargs[List[T]]],
    ) -> Optional[List[T]]:
        """Asynchronously executes a multi-choice decision-making process, generating a prompt based on the instruction and options, and validates the returned selection results.

        Args:
            instruction (str): The user-provided instruction/question description.
            choices (List[T]): A list of candidate options, requiring elements to have `name` and `briefing` fields.
            k (NonNegativeInt): The number of choices to select, 0 means infinite. Defaults to 0.
            is_included_fn (Optional[Callable[[Set[str],T], bool]] = None): A function to check whether a choice is included in the query.
            send_to (Optional[str]): The group name of which the requests will be sent.
            **kwargs (Unpack[ValidateKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            Optional[List[T]]: The final validated selection result list, with element types matching the input `choices`.
        """
        from fabricatio_core.rust import json_parser

        def _is_included_fn(query: Set[str], choice: T) -> bool:
            return choice.name in query

        is_included_fn = _is_included_fn if is_included_fn is None else is_included_fn

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
            q = json_parser.validate_set(response, elements_type=str, length=k)

            if q is None:
                return None

            final_ret = [cho for cho in choices if is_included_fn(q, cho)]

            if not final_ret or (k and final_ret != k):
                logger.error(f"Invalid choices that nothing got selected: {q}")

            return final_ret

        return cast(
            "List[T]",
            await self.aask_validate(
                question=prompt,
                validator=_validate,
                send_to=send_to,
                **kwargs,
            ),
        )

    async def aenum_choose[E: (StrEnum, IntEnum)](
        self,
        instruction: str,
        enum_type: Type[E],
        k: NonNegativeInt = 0,
        send_to: Optional[str] = None,
        **kwargs: Unpack[ValidateKwargs[List[E]]],
    ) -> Optional[List[E]]:
        """Asynchronously selects enum members from the given enum type based on the instruction.

        Mimics :meth:`achoose` but operates on ``StrEnum`` / ``IntEnum`` members instead of
        ``WithBriefing`` objects.  Each member's *name* is used as the choice identifier.
        The enum class ``__doc__`` is passed as ``enum_doc`` to the template for context.

        Args:
            instruction (str): The user-provided instruction/question description.
            enum_type (Type[E]): The enum type to select from.
            k (NonNegativeInt): The number of choices to select, 0 means all relevant. Defaults to 0.
            send_to (Optional[str]): The group name of which the requests will be sent.
            **kwargs (Unpack[ValidateKwargs[List[E]]]): Additional keyword arguments for the LLM usage.

        Returns:
            Optional[List[E]]: The selected enum member(s), or None if validation fails.
        """
        from fabricatio_core.rust import json_parser

        choices = list(enum_type)
        prompt = TEMPLATE_MANAGER.render_template(
            CONFIG.templates.make_enum_choice_template,
            {
                "options": [m.name for m in enum_type],
                "enum_doc": enum_type.__doc__,
                "k": k,
                "instruction": instruction,
            },
        )
        names = {c.name for c in choices}

        logger.debug(f"Start choosing between {names} with prompt: \n{prompt}")

        def _validate(response: str) -> List[E] | None:
            q = json_parser.validate_set(response, elements_type=str, length=k)

            if q is None:
                return None

            final_ret = [cho for cho in choices if cho.name in q]

            if not final_ret or (k and len(final_ret) != k):
                logger.error(f"Invalid enum choices: {q}")
                return None

            return final_ret

        return cast(
            "List[E]",
            await self.aask_validate(
                question=prompt,
                validator=_validate,
                send_to=send_to,
                **kwargs,
            ),
        )

    async def apick[T: WithBriefing](
        self,
        instruction: str,
        choices: List[T],
        send_to: Optional[str] = None,
        **kwargs: Unpack[ValidateKwargs[List[T]]],
    ) -> T:
        """Asynchronously picks a single choice from a list of options using AI validation.

        Args:
            instruction (str): The user-provided instruction/question description.
            choices (List[T]): A list of candidate options, requiring elements to have `name` and `briefing` fields.
            send_to (Optional[str]): The group name of which the requests will be sent.
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
                send_to=send_to,
                **kwargs,
            ),
        )[0]

    @overload
    async def ajudge(
        self,
        prompt: str,
        affirm_case: str = "",
        deny_case: str = "",
        send_to: Optional[str] = None,
        **kwargs: Unpack[ValidateKwargs[bool]],
    ) -> Optional[bool]: ...

    @overload
    async def ajudge(
        self,
        prompt: List[str],
        affirm_case: str = "",
        deny_case: str = "",
        send_to: Optional[str] = None,
        **kwargs: Unpack[ValidateKwargs[bool]],
    ) -> List[Optional[bool]] | None: ...

    async def ajudge(
        self,
        prompt: str | List[str],
        affirm_case: str = "",
        deny_case: str = "",
        send_to: Optional[str] = None,
        **kwargs: Unpack[ValidateKwargs[bool]],
    ) -> Optional[bool] | List[Optional[bool]]:
        """Asynchronously judges a prompt using AI validation.

        Args:
            prompt (str): The input prompt to be judged.
            affirm_case (str): The affirmative case for the AI model. Defaults to an empty string.
            deny_case (str): The negative case for the AI model. Defaults to an empty string.
            send_to (Optional[str]): The group name of which the requests will be sent.
            **kwargs (Unpack[ValidateKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            bool: The judgment result (True or False) based on the AI's response.
        """
        params = self._resolve_validation_params(**kwargs)
        resolved_send_to = self._resolve_completion_send_to(send_to=send_to)
        return await rust.router_usage.judging(
            requirement=prompt,
            affirm_case=affirm_case,
            deny_case=deny_case,
            send_to=resolved_send_to,
            **params,
        )


class UseEmbedding(EmbeddingScopedConfig, ABC):
    """A class representing the embedding model.

    This class extends LLMUsage and provides methods to generate embeddings for input text using various models.
    """

    @overload
    async def vectorize(self, input_text: List[str], **kwargs: Unpack[EmbeddingKwargs]) -> List[List[float]]: ...

    @overload
    async def vectorize(self, input_text: str, **kwargs: Unpack[EmbeddingKwargs]) -> List[float]: ...

    @overload
    async def vectorize(
        self, input_text: List[str] | str, **kwargs: Unpack[EmbeddingKwargs]
    ) -> List[List[float]] | List[float]: ...

    async def vectorize(
        self, input_text: List[str] | str, **kwargs: Unpack[EmbeddingKwargs]
    ) -> List[List[float]] | List[float]:
        """Asynchronously generates vector embeddings for the given input text.

        Args:
            input_text (List[str] | str): A string or list of strings to generate embeddings for.
            **kwargs (Unpack[EmbeddingKwargs]): Additional keyword arguments for the embedding model.

        Returns:
            List[List[float]] | List[float]: The generated embeddings.
        """
        kw = self._resolve_embedding_params(**kwargs)
        is_text = False

        if isinstance(input_text, str):
            input_text = [input_text]
            is_text = True
        res = await rust.ROUTER.embedding(texts=input_text, **kw)

        return res[0] if is_text else res


class UseReranker(RerankerScopedConfig, ABC):
    """A class for reranking documents using a reranker model."""

    async def arank(
        self, query: str, documents: List[str], **kwargs: Unpack[RerankerKwargs]
    ) -> List[Tuple[int, float]]:
        """Reranks a list of documents based on their relevance to the query.

        Args:
            query: The query text to rank documents against.
            documents: A list of document texts to rerank.
            **kwargs: Additional keyword arguments for the reranker model.

        Returns:
            List[Tuple[int, float]]: A list of (document_index, score) pairs sorted by relevance descending.
        """
        kw = self._resolve_reranker_params(**kwargs)
        return await rust.ROUTER.rerank(query=query, documents=documents, **kw)
