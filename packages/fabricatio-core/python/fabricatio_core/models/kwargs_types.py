"""This module contains the types for the keyword arguments of the methods in the models module."""

from typing import TypedDict


class RouteKwargs(TypedDict, total=False):
    """Configuration parameters for routing operations.

    These arguments control the behavior of routing models,
    such as the number of attempts to make before giving up.
    """

    no_cache: bool


class EmbeddingKwargs(RouteKwargs, total=False):
    """Configuration parameters for text embedding operations.

    These settings control the behavior of embedding models that convert text
    to vector representations.
    """

    send_to: str
    """Router group name used for embedding requests. Free-form string."""

    ndim: int

    max_batch_emb_size: int


class RerankerKwargs(RouteKwargs, total=False):
    """Configuration parameters for text reranking operations.

    These arguments control the behavior of reranking models,
    such as the number of attempts to make before giving up.
    """

    send_to: str
    """Router group name used for reranking requests. Free-form string."""


class LLMKwargs(RouteKwargs, total=False):
    """Configuration parameters for language model inference.

    These arguments control the behavior of large language model calls,
    including generation parameters, caching options, and optional images.
    """

    stream: bool
    effort: str | None
    temperature: float | None
    top_p: float | None
    max_completion_tokens: int | None
    presence_penalty: float | None
    frequency_penalty: float | None
    images: list[bytes] | None


class ValidateKwargs[T](LLMKwargs, total=False):
    """Arguments for content validation operations.

    Extends LLMKwargs with additional parameters specific to validation tasks,
    such as limiting the number of validation attempts.
    """

    default: T | None
    max_validations: int


class MappingKwargs[K: int | str | bool, V: int | str | bool | float](ValidateKwargs[dict[K, V]], total=False):
    """Arguments for mapping operations.

    Extends RouteKwargs with parameters for mapping operations,
    such as the number of attempts to make before giving up.
    """

    k: int
    key_type: type[K]
    value_type: type[V]


class ChooseKwargs[T](ValidateKwargs[list[T]], total=False):
    """Arguments for selection operations.

    Extends LLMKwargs with parameters for selecting among options,
    such as the number of items to choose.
    """

    k: int


class ListingKwargs[T: int | str | bool | float](ChooseKwargs[T], total=False):
    """Arguments for operations that return a list of items without exposing value_type."""


class ListValueKwargs[T: int | str | bool | float](ChooseKwargs[T], total=False):
    """Arguments for operations that return a list of typed values."""

    value_type: type[T]
