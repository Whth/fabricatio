"""This module contains the types for the keyword arguments of the methods in the models module."""

from typing import List, Optional, TypedDict


class RouteKwargs(TypedDict, total=False):
    """Configuration parameters for routing operations.

    These arguments control the behavior of routing models,
    such as the number of attempts to make before giving up.
    """

    send_to: str
    no_cache: bool


class EmbeddingKwargs(RouteKwargs, total=False):
    """Configuration parameters for text embedding operations.

    These settings control the behavior of embedding models that convert text
    to vector representations.
    """


class LLMKwargs(RouteKwargs, total=False):
    """Configuration parameters for language model inference.

    These arguments control the behavior of large language model calls,
    including generation parameters and caching options.
    """

    stream: bool
    temperature: Optional[float]
    top_p: Optional[float]
    max_completion_tokens: Optional[int]
    presence_penalty: Optional[float]
    frequency_penalty: Optional[float]


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
