"""This module contains the types for the keyword arguments of the methods in the models module."""

from typing import List, NotRequired, TypedDict

from pydantic import NonNegativeFloat, NonNegativeInt, PositiveInt


class CollectionSimpleConfigKwargs(TypedDict):
    """A type representing the configuration for a collection."""

    dimension: NotRequired[int]
    timeout: NotRequired[float]


class FetchKwargs(TypedDict):
    """A type representing the keyword arguments for the fetch method."""

    collection_name: NotRequired[str]
    similarity_threshold: NotRequired[float]
    result_per_query: NotRequired[int]


class EmbeddingKwargs(TypedDict):
    """A type representing the keyword arguments for the embedding method."""

    model: NotRequired[str]
    dimensions: NotRequired[int]
    timeout: NotRequired[PositiveInt]
    caching: NotRequired[bool]


class LLMKwargs(TypedDict):
    """A type representing the keyword arguments for the LLM (Large Language Model) usage."""

    model: NotRequired[str]
    temperature: NotRequired[NonNegativeFloat]
    stop: NotRequired[str | List[str]]
    top_p: NotRequired[NonNegativeFloat]
    max_tokens: NotRequired[PositiveInt]
    stream: NotRequired[bool]
    timeout: NotRequired[PositiveInt]
    max_retries: NotRequired[PositiveInt]


class ValidateKwargs(LLMKwargs):
    """A type representing the keyword arguments for the validate method."""

    max_validations: NotRequired[PositiveInt]


class GenerateKwargs(ValidateKwargs):
    """A type representing the keyword arguments for the generate method."""

    system_message: NotRequired[str]


class ChooseKwargs(GenerateKwargs):
    """A type representing the keyword arguments for the choose method."""

    k: NotRequired[NonNegativeInt]
