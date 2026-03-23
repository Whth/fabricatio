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

import asyncio
import traceback
from abc import ABC
from asyncio import gather
from os import PathLike
from pathlib import Path
from typing import Callable, Dict, List, Optional, Self, Set, Type, Unpack, overload

from more_itertools import duplicates_everseen
from pydantic import NonNegativeInt, PositiveInt

from fabricatio_core.decorators import logging_exec_time, once
from fabricatio_core.models.containers import CodeSnippet
from fabricatio_core.models.generic import EmbeddingScopedConfig, LLMScopedConfig, WithBriefing
from fabricatio_core.models.kwargs_types import ChooseKwargs, EmbeddingKwargs, LLMKwargs, ValidateKwargs
from fabricatio_core.rust import (
    CONFIG,
    TEMPLATE_MANAGER,
    ProviderType,
    SecretStr,
    logger,
)
from fabricatio_core.utils import first_available, ok


class UseRouter:
    """A router class for managing LLM provider configurations and model deployments.

    This class provides methods to register AI providers and deploy completion or embedding models
    with optional rate limiting configurations. It follows a fluent interface pattern, returning
    itself to allow method chaining.
    """

    @classmethod
    async def add_provider(
        cls,
        provider_type: ProviderType,
        name: str | None = None,
        api_key: SecretStr | None = None,
        endpoint: str | None = None,
    ) -> Type[Self]:
        """Registers a new AI provider with the system.

        Args:
            provider_type (ProviderType): The type of the provider to add.
            name (str | None): Optional custom name for the provider. If None, a default name is used.
            api_key (str | None): Optional API key for authentication.
            endpoint (str | None): Optional custom endpoint URL for the provider.

        Returns:
            None
        """
        await add_provider(provider_type, name, api_key, endpoint)
        return cls

    @classmethod
    async def deploy_completion_model(
        cls,
        group: str,
        model_identifier: str,
        rpm: int | None = None,
        tpm: int | None = None,
    ) -> Type[Self]:
        """Asynchronously deploys a completion model to a specified group.

        Args:
            group (str): The group identifier to deploy the model to.
            model_identifier (str): The unique identifier of the model to deploy.
            rpm (int | None): Optional requests per minute rate limit.
            tpm (int | None): Optional tokens per minute rate limit.

        Returns:
            None
        """
        await add_completion_model(
            group,
            model_identifier,
            rpm,
            tpm,
        )
        return cls

    @classmethod
    async def deploy_embedding_model(
        cls, group: str, model_identifier: str, rpm: int | None = None, tpm: int | None = None
    ) -> Type[Self]:
        """Asynchronously deploys an embedding model to a specified group.

        Args:
            group (str): The group identifier to deploy the model to.
            model_identifier (str): The unique identifier of the model to deploy.
            rpm (int | None): Optional requests per minute rate limit.
            tpm (int | None): Optional tokens per minute rate limit.

        Returns:
            None
        """
        await add_embedding_model(
            group,
            model_identifier,
            rpm,
            tpm,
        )

        return cls

    @classmethod
    async def mount_cache(cls, file_path: str | Path | PathLike | None = None) -> Type[Self]:
        """Mount the cache database to the Routers."""
        await mount_cache(
            ok(
                file_path or CONFIG.routing.cache_database_path,
                "Cache database file path is not specified at any where!",
            )
        )
        return cls

    @classmethod
    @once
    async def establish_from_config(cls) -> Type[Self]:
        """Add providers, models from the configurations."""
        logger.debug("Deploying providers and models from the configurations.")
        await asyncio.gather(
            *[add_provider(p.provider_type, p.name, p.api_key, p.api_endpoint) for p in CONFIG.routing.providers]
        )

        await asyncio.gather(
            *[
                add_completion_model(d.group, d.identifier, d.rpm, d.tpm)
                for d in CONFIG.routing.completion_model_deployments
            ],
            *[
                add_embedding_model(d.group, d.identifier, d.rpm, d.tpm)
                for d in CONFIG.routing.embedding_model_deployments
            ],
        )
        return cls


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
        send_to: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_completion_tokens: Optional[int] = None,
        stream: Optional[bool] = None,
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

        def _resolve_config() -> LLMKwargs:
            return LLMKwargs(
                send_to=ok(send_to or self.llm_send_to or CONFIG.llm.send_to, "send_to is not specified at any where"),
                temperature=first_available((temperature, self.llm_temperature, CONFIG.llm.temperature)),
                top_p=first_available((top_p, self.llm_top_p, CONFIG.llm.top_p)),
                max_completion_tokens=ok(
                    max_completion_tokens or self.llm_max_completion_tokens or CONFIG.llm.max_completion_tokens
                ),
                stream=first_available((stream, self.llm_stream, CONFIG.llm.stream)),
                presence_penalty=first_available(
                    (presence_penalty, self.llm_presence_penalty, CONFIG.llm.presence_penalty)
                ),
                frequency_penalty=first_available(
                    (frequency_penalty, self.llm_frequency_penalty, CONFIG.llm.frequency_penalty)
                ),
            )

        kw = _resolve_config()

        if isinstance(question, str):
            return await completion(message=question, **kw)

        if isinstance(question, list):
            return await asyncio.gather(*[completion(message=q, **kw) for q in question])
        raise NotImplementedError("Question must be either a string or a list of strings.")

    @overload
    async def aask_validate[T](
        self,
        question: str,
        validator: Callable[[str], T | None],
        default: T = ...,
        max_validations: PositiveInt = 2,
        **kwargs: Unpack[LLMKwargs],
    ) -> T: ...

    @overload
    async def aask_validate[T](
        self,
        question: List[str],
        validator: Callable[[str], T | None],
        default: T = ...,
        max_validations: PositiveInt = 2,
        **kwargs: Unpack[LLMKwargs],
    ) -> List[T]: ...

    @overload
    async def aask_validate[T](
        self,
        question: str,
        validator: Callable[[str], T | None],
        default: None = None,
        max_validations: PositiveInt = 2,
        **kwargs: Unpack[LLMKwargs],
    ) -> Optional[T]: ...

    @overload
    async def aask_validate[T](
        self,
        question: List[str],
        validator: Callable[[str], T | None],
        default: None = None,
        max_validations: PositiveInt = 2,
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
            **kwargs (Unpack[LLMKwargs]): Additional keyword arguments for the LLM usage.

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
                validator=GenericCapture.capture,
                **kwargs,
            )
        if isinstance(requirement, list):
            return await self.aask_validate(
                TEMPLATE_MANAGER.render_template(
                    CONFIG.templates.generic_string_template,
                    [{"requirement": r, "language": GenericCapture.capture_type} for r in requirement],
                ),
                validator=GenericCapture.capture,
                **kwargs,
            )
        return None

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
        from fabricatio_core.parser import Capture

        cap = Capture.capture_code_block(code_language)

        return await self.aask_validate(
            TEMPLATE_MANAGER.render_template(
                CONFIG.templates.code_string_template,
                {"requirement": requirement, "code_language": code_language}
                if isinstance(requirement, str)
                else [{"requirement": r, "code_language": code_language} for r in requirement],
            ),
            validator=cap.capture,
            **kwargs,
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
        from fabricatio_core.parser import Capture

        cap = Capture.capture_snippet()

        def _validator(resp: str) -> Optional[List[CodeSnippet]]:
            matches = cap.capture_all(resp)
            if not matches:
                return None
            return [CodeSnippet(source=src, write_to=pth) for pth, src in matches]

        return await self.aask_validate(
            TEMPLATE_MANAGER.render_template(
                CONFIG.templates.code_snippet_template,
                {"requirement": requirement, "code_language": code_language}
                if isinstance(requirement, str)
                else [{"requirement": r, "code_language": code_language} for r in requirement],
            ),
            validator=_validator,
            **kwargs,
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
        from fabricatio_core.parser import JsonCapture

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
            ret = JsonCapture.validate_with(response, target_type=List, elements_type=str, length=k)
            if ret is None:
                return None
            q = set(ret)
            final_ret = [cho for cho in choices if is_included_fn(q, cho)]

            if ret and not final_ret:
                logger.error(f"Invalid choices that nothing got selected: {ret}")
                return None

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

        def _resolve_config() -> EmbeddingKwargs:
            return EmbeddingKwargs(
                send_to=ok(
                    send_to or self.embedding_send_to or CONFIG.embedding.send_to,
                    "send_to is not specified at any where",
                ),
            )

        kw = _resolve_config()
        if isinstance(input_text, str):
            return (await embedding(texts=[input_text], **kw))[0]

        if isinstance(input_text, list):
            return await embedding(texts=input_text, **kw)
        raise NotImplementedError("Question must be either a string or a list of strings.")
