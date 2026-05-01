"""This module contains the types for the keyword arguments of the methods in the models module."""

from typing import List, Optional, TypedDict


class EmbeddingKwargs(TypedDict, total=False):
    """Configuration parameters for text embedding operations.

    These settings control the behavior of embedding models that convert text
    to vector representations.
    """

    send_to: str
    no_cache: bool


class LLMKwargs(TypedDict, total=False):
    """Configuration parameters for language model inference.

    These arguments control the behavior of large language model calls,
    including generation parameters and caching options.

    Attributes:
        no_cache: If True, bypass the response cache and force a fresh inference.
    """

    send_to: str
    stream: bool
    temperature: Optional[float]
    top_p: Optional[float]
    max_completion_tokens: Optional[int]
    presence_penalty: Optional[float]
    frequency_penalty: Optional[float]
    no_cache: bool


class ValidateKwargs[T](LLMKwargs, total=False):
    """Arguments for content validation operations.

    Extends LLMKwargs with additional parameters specific to validation tasks,
    such as limiting the number of validation attempts.
    """

    default: Optional[T]
    max_validations: int


class ChooseKwargs[T](ValidateKwargs[List[T]], total=False):
    """Arguments for selection operations.

    Extends LLMKwargs with parameters for selecting among options,
    such as the number of items to choose.
    """

    k: int


class ListStringKwargs(ChooseKwargs[str], total=False):
    """Arguments for operations that return a list of strings."""
