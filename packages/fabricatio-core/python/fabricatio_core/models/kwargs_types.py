"""This module contains the types for the keyword arguments of the methods in the models module."""

from typing import List, Optional, TypedDict


class EmbeddingKwargs(TypedDict, total=False):
    """Configuration parameters for text embedding operations.

    These settings control the behavior of embedding models that convert text
    to vector representations.
    """

    model: str
    dimensions: int
    timeout: int
    caching: bool


class LLMKwargs(TypedDict, total=False):
    """Configuration parameters for language model inference.

    These arguments control the behavior of large language model calls,
    including generation parameters and caching options.
    """

    model: Optional[str]
    temperature: float
    stop: str | list[str]
    top_p: float
    max_tokens: int
    stream: bool
    timeout: int
    max_retries: int
    no_cache: bool  # if the req uses cache in this call
    no_store: bool  # If store the response of this call to cache
    cache_ttl: int  # how long the stored cache is alive, in seconds
    s_maxage: int  # max accepted age of cached response, in seconds
    presence_penalty: float
    frequency_penalty: float


class GenerateKwargs(LLMKwargs, total=False):
    """Arguments for content generation operations.

    Extends LLMKwargs with additional parameters specific to generation tasks,
    such as the number of generated items and the system message.
    """

    system_message: str


class ValidateKwargs[T](GenerateKwargs, total=False):
    """Arguments for content validation operations.

    Extends LLMKwargs with additional parameters specific to validation tasks,
    such as limiting the number of validation attempts.
    """

    default: Optional[T]
    max_validations: int


class ChooseKwargs[T](ValidateKwargs[List[T]], total=False):
    """Arguments for selection operations.

    Extends GenerateKwargs with parameters for selecting among options,
    such as the number of items to choose.
    """

    k: int


class ListStringKwargs(ChooseKwargs[str], total=False):
    """Arguments for operations that return a list of strings."""
