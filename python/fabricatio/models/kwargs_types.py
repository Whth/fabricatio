"""This module contains the types for the keyword arguments of the methods in the models module."""

from typing import Dict, List, NotRequired, Optional, Required, TypedDict


class ChunkKwargs(TypedDict):
    """Configuration parameters for chunking operations."""

    max_chunk_size: int
    max_overlapping_rate: NotRequired[float]


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


class CompositeScoreKwargs(ValidateKwargs[List[Dict[str, float]]], total=False):
    """Arguments for composite score generation operations.

    Extends GenerateKwargs with parameters for generating composite scores
    based on specific criteria and weights.
    """

    topic: str
    criteria: set[str]
    weights: Dict[str, float]
    manual: Dict[str, str]


class BestKwargs(CompositeScoreKwargs, total=False):
    """Arguments for choose top-k operations."""

    k: int


class ReviewInnerKwargs[T](ValidateKwargs[T], total=False):
    """Arguments for content review operations."""

    criteria: set[str]


# noinspection PyTypedDict
class ReviewKwargs[T](ReviewInnerKwargs[T], total=False):
    """Arguments for content review operations.

    Extends GenerateKwargs with parameters for evaluating content against
    specific topics and review criteria.
    """

    rating_manual: Dict[str, str]
    topic: Required[str]


class ReferencedKwargs[T](ValidateKwargs[T], total=False):
    """Arguments for content review operations."""

    reference: str


# noinspection PyTypedDict
class ChooseKwargs[T](ValidateKwargs[T], total=False):
    """Arguments for selection operations.

    Extends GenerateKwargs with parameters for selecting among options,
    such as the number of items to choose.
    """

    k: int
