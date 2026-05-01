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
from typing import Callable, Dict, List, Optional, Set, Unpack, overload

from more_itertools import duplicates_everseen
from pydantic import NonNegativeInt, PositiveInt

from fabricatio_core import rust
from fabricatio_core.decorators import logging_exec_time
from fabricatio_core.models.generic import EmbeddingScopedConfig, LLMScopedConfig, WithBriefing
from fabricatio_core.models.kwargs_types import ChooseKwargs, LLMKwargs, ValidateKwargs
from fabricatio_core.rust import CONFIG, TEMPLATE_MANAGER, CodeSnippet, logger
from fabricatio_core.utils import ok


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
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_completion_tokens: Optional[int] = None,
        stream: Optional[bool] = None,
        presence_penalty: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
    ) -> List[str]: ...

    @overload
    async def aask(
        self,
        question: str,
        send_to: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_completion_tokens: Optional[int] = None,
        stream: Optional[bool] = None,
        presence_penalty: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
    ) -> str: ...

    @logging_exec_time
    async def aask(
        self,
        question: str | List[str],
        stream: Optional[bool] = None,
        send_to: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_completion_tokens: Optional[int] = None,
        presence_penalty: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
    ) -> str | List[str]:
        """Asynchronously asks the language model a question and returns the response content.

        Args:
            question (str | List[str]): The question or list of questions to ask the model.
            send_to (Optional[str]): The target namespace for the request. If None, uses the default `llm_send_to`.
            temperature (Optional[float]): Sampling temperature for response generation. If None, uses `llm_temperature`.
            top_p (Optional[float]): Nucleus sampling parameter. If None, uses `llm_top_p`.
            max_completion_tokens (Optional[int]): Maximum number of tokens to generate. If None, uses `llm_max_completion_tokens`.
            stream (Optional[bool]): Whether to stream the response. If None, uses `llm_stream`.
            presence_penalty (Optional[float]): Presence penalty for response generation. If None, uses `llm_presence_penalty`.
            frequency_penalty (Optional[float]): Frequency penalty for response generation. If None, uses `llm_frequency_penalty`.

        Returns:
            str | List[str]: The content of the model's response message. Returns a single string if input is a string,
                or a list of strings if input is a list of strings.
        """
        kw = self._resolve_completion_params(
            stream=stream,
            send_to=send_to,
            temperature=temperature,
            top_p=top_p,
            max_completion_tokens=max_completion_tokens,
            presence_penalty=presence_penalty,
            frequency_penalty=frequency_penalty,
        )

        return await rust.router_usage.ask(question=question, **kw)

    @overload
    async def aask_validate[T](
        self,
        question: str,
        validator: Callable[[str], T | None],
        default: T = ...,
        max_validations: PositiveInt = 3,
        **kwargs: Unpack[LLMKwargs],
    ) -> T: ...

    @overload
    async def aask_validate[T](
        self,
        question: List[str],
        validator: Callable[[str], T | None],
        default: T = ...,
        max_validations: PositiveInt = 3,
        **kwargs: Unpack[LLMKwargs],
    ) -> List[T]: ...

    @overload
    async def aask_validate[T](
        self,
        question: str,
        validator: Callable[[str], T | None],
        default: None = None,
        max_validations: PositiveInt = 3,
        **kwargs: Unpack[LLMKwargs],
    ) -> Optional[T]: ...

    @overload
    async def aask_validate[T](
        self,
        question: List[str],
        validator: Callable[[str], T | None],
        default: None = None,
        max_validations: PositiveInt = 3,
        **kwargs: Unpack[LLMKwargs],
    ) -> List[Optional[T]]: ...

    async def aask_validate[T](
        self,
        question: str | List[str],
        validator: Callable[[str], T | None],
        default: Optional[T] = None,
        max_validations: PositiveInt = 3,
        **kwargs: Unpack[LLMKwargs],
    ) -> None | T | List[Optional[T]] | List[T]:
        """Asynchronously asks a question and validates the response using a given validator.

        Args:
            question (str | List[str]): The question to ask.
            validator (Callable[[str], T | None]): A function to validate the response.
            default (T | None): Default value to return if validation fails. Defaults to None.
            max_validations (PositiveInt): Maximum number of validation attempts. Defaults to 3.
            **kwargs (Unpack[LLMKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            Optional[T] | List[T | None] | List[T] | T: The validated response.
        """

        async def _inner(q: str) -> Optional[T]:
            for lap in range(max_validations):
                try:
                    if (validated := validator(response := await self.aask(question=q, **kwargs))) is not None:
                        logger.debug(f"Successfully validated the response at {lap}th attempt.")
                        return validated
                except Exception as e:  # noqa: BLE001
                    logger.error(f"Error during validation:\n{e}")
                    logger.debug(traceback.format_exc())
                    break
                logger.error(f"Failed to validate the response at {lap}th attempt:\n{response}")

            if default is None:
                logger.error(f"Failed to validate the response after {max_validations} attempts.")
            return default

        return await (gather(*[_inner(q) for q in question]) if isinstance(question, list) else _inner(question))

    @overload
    async def amapping_str(
        self, requirement: str, k: NonNegativeInt = 0, **kwargs: Unpack[ValidateKwargs[Dict[str, str]]]
    ) -> Optional[Dict[str, str]]: ...

    @overload
    async def amapping_str(
        self, requirement: List[str], k: NonNegativeInt = 0, **kwargs: Unpack[ValidateKwargs[Dict[str, str]]]
    ) -> List[Optional[Dict[str, str]]] | None: ...

    async def amapping_str(
        self, requirement: str | List[str], k: NonNegativeInt = 0, **kwargs: Unpack[ValidateKwargs[Dict[str, str]]]
    ) -> None | Dict[str, str] | List[Optional[Dict[str, str]]]:
        """Asynchronously generates a mapping of strings based on a given requirement.

        Args:
            requirement (str): The requirement for the mapping of strings.
            k (NonNegativeInt): The number of choices to select, 0 means infinite. Defaults to 0.
            **kwargs (Unpack[ValidateKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            Optional[Dict[str, str]]: The validated response as a mapping of strings.
        """
        params = self._resolve_validation_params(**kwargs)
        return await rust.router_usage.mapping_strings(
            requirement=requirement,
            k=k,
            **params,
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
        return await rust.router_usage.listing_strings(
            requirement=requirement, k=k, **self._resolve_validation_params(**kwargs)
        )

    async def apathstr(self, requirement: str, **kwargs: Unpack[ChooseKwargs[str]]) -> Optional[List[str]]:
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
            **kwargs (Unpack[LLMKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            Optional[str]: The generated string.
        """
        return await rust.router_usage.generic_string(
            requirement=requirement, **self._resolve_validation_params(**kwargs)
        )

    @overload
    async def acode_string(
        self, requirement: str, code_language: Optional[str] = None, **kwargs: Unpack[ValidateKwargs[str]]
    ) -> Optional[str]: ...

    @overload
    async def acode_string(
        self, requirement: List[str], code_language: Optional[str] = None, **kwargs: Unpack[ValidateKwargs[str]]
    ) -> List[Optional[str]]: ...

    async def acode_string(
        self, requirement: str | List[str], code_language: Optional[str] = None, **kwargs: Unpack[ValidateKwargs[str]]
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
        return await rust.router_usage.code_string(
            requirement=requirement, code_language=code_language, **self._resolve_validation_params(**kwargs)
        )

    @overload
    async def acode_snippets(
        self,
        requirement: str,
        code_language: Optional[str] = None,
        **kwargs: Unpack[ValidateKwargs[List[CodeSnippet]]],
    ) -> Optional[List[CodeSnippet]]: ...

    @overload
    async def acode_snippets(
        self,
        requirement: List[str],
        code_language: Optional[str] = None,
        **kwargs: Unpack[ValidateKwargs[List[CodeSnippet]]],
    ) -> List[List[CodeSnippet] | None] | None: ...

    async def acode_snippets(
        self,
        requirement: str | List[str],
        code_language: Optional[str] = None,
        **kwargs: Unpack[ValidateKwargs[List[CodeSnippet]]],
    ) -> None | List[CodeSnippet] | List[List[CodeSnippet] | None]:
        """Asynchronously generates code snippets based on given requirements and code language.

        Args:
            requirement (str | List[str]): The requirement(s) for generating code snippets.
            code_language (Optional[str]): The programming language for the generated code. Defaults to None.
            **kwargs (Unpack[ValidateKwargs[List[CodeSnippet]]]): Additional keyword arguments for the LLM usage.

        Returns:
            None | List[CodeSnippet] | List[List[CodeSnippet] | None]: The generated code snippet(s).
            Returns a list of CodeSnippet objects if requirement is a string, or a list of lists of
            CodeSnippet objects or None if requirement is a list.
        """
        return await rust.router_usage.code_snippets(
            requirement=requirement, code_language=code_language, **self._resolve_validation_params(**kwargs)
        )

    async def achoose[T: WithBriefing](
        self,
        instruction: str,
        choices: List[T],
        k: NonNegativeInt = 0,
        is_included_fn: Optional[Callable[[Set[str], T], bool]] = None,
        **kwargs: Unpack[ValidateKwargs[List[T]]],
    ) -> Optional[List[T]]:
        """Asynchronously executes a multi-choice decision-making process, generating a prompt based on the instruction and options, and validates the returned selection results.

        Args:
            instruction (str): The user-provided instruction/question description.
            choices (List[T]): A list of candidate options, requiring elements to have `name` and `briefing` fields.
            k (NonNegativeInt): The number of choices to select, 0 means infinite. Defaults to 0.
            is_included_fn (Optional[Callable[[Set[str],T], bool]] = None): A function to check whether a choice is included in the query.
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

    @overload
    async def ajudge(
        self,
        prompt: str,
        affirm_case: str = "",
        deny_case: str = "",
        **kwargs: Unpack[ValidateKwargs[bool]],
    ) -> Optional[bool]: ...

    @overload
    async def ajudge(
        self,
        prompt: List[str],
        affirm_case: str = "",
        deny_case: str = "",
        **kwargs: Unpack[ValidateKwargs[bool]],
    ) -> List[Optional[bool]] | None: ...

    async def ajudge(
        self,
        prompt: str | List[str],
        affirm_case: str = "",
        deny_case: str = "",
        **kwargs: Unpack[ValidateKwargs[bool]],
    ) -> Optional[bool] | List[Optional[bool]]:
        """Asynchronously judges a prompt using AI validation.

        Args:
            prompt (str): The input prompt to be judged.
            affirm_case (str): The affirmative case for the AI model. Defaults to an empty string.
            deny_case (str): The negative case for the AI model. Defaults to an empty string.
            **kwargs (Unpack[ValidateKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            bool: The judgment result (True or False) based on the AI's response.
        """
        return await rust.router_usage.judging(
            requirement=prompt,
            affirm_case=affirm_case,
            deny_case=deny_case,
            **self._resolve_validation_params(**kwargs),
        )


class UseEmbedding(UseLLM, EmbeddingScopedConfig, ABC):
    """A class representing the embedding model.

    This class extends LLMUsage and provides methods to generate embeddings for input text using various models.
    """

    @overload
    async def vectorize(self, input_text: List[str], send_to: str | None = None) -> List[List[float]]: ...

    @overload
    async def vectorize(self, input_text: str, send_to: str | None = None) -> List[float]: ...

    async def vectorize(
        self, input_text: List[str] | str, send_to: str | None = None
    ) -> List[List[float]] | List[float]:
        """Asynchronously generates vector embeddings for the given input text.

        Args:
            input_text (List[str] | str): A string or list of strings to generate embeddings for.
            send_to (str | None): The namespace to send the request to. Defaults to None.

        Returns:
            List[List[float]] | List[float]: The generated embeddings.
        """
        kw = self._resolve_embedding_params(send_to=send_to)
        is_text = False

        if isinstance(input_text, str):
            input_text = [input_text]
            is_text = True
        res = await rust.ROUTER.embedding(texts=input_text, **kw)

        return res[0] if is_text else res
