"""This module contains the types for the keyword arguments of the methods in the models module."""

from typing import List, NotRequired, TypedDict

from pydantic import NonNegativeFloat, NonNegativeInt, PositiveInt


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


class ChooseKwargs(LLMKwargs):
    """A type representing the keyword arguments for the choose method."""

    max_validations: NotRequired[PositiveInt]
    system_message: NotRequired[str]
    k: NotRequired[NonNegativeInt]
