"""A module that provides capabilities to summarize raw text into a length-bounded summary."""

import re
from abc import ABC
from enum import StrEnum
from typing import Unpack

from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.models.kwargs_types import LLMKwargs
from pydantic import PositiveInt

from fabricatio_capabilities.config import capabilities_config

_SENTENCE_SPLIT = re.compile(r"[^.!?。！？]+(?:[.!?。！？]+|$)")


class LengthType(StrEnum):
    """Units for measuring text length."""

    Chars = "chars"
    """Count individual characters."""

    Words = "words"
    """Count whitespace-separated words."""

    Sentences = "sentences"
    """Count sentences, split on ``.`` ``!`` ``?`` and their full-width variants."""


def _length(text: str, length_type: LengthType) -> int:
    """Count the length of *text* in the given unit."""
    match length_type:
        case LengthType.Chars:
            return len(text)
        case LengthType.Words:
            return len(text.split())
        case LengthType.Sentences:
            return len(_SENTENCE_SPLIT.findall(text))


def _resolve_bounds(min_length: int | None, max_length: int | None) -> tuple[int | None, int | None]:
    """Resolve the effective [min, max] length window.

    ``None`` bounds stay open; a ``None`` floor with a set ceiling derives 80% of
    the ceiling (integer floor, at least 1). Both bounds ``None`` means the output
    length is unconstrained.

    Raises:
        ValueError: If any explicit bound is not a positive integer, or the
            explicit window is empty (``min_length > max_length``).
    """
    if max_length is not None and max_length < 1:
        raise ValueError(f"max_length must be a positive integer, got {max_length}.")
    if min_length is not None and min_length < 1:
        raise ValueError(f"min_length must be a positive integer, got {min_length}.")
    if min_length is not None and max_length is not None and min_length > max_length:
        raise ValueError(f"min_length must not exceed max_length, got {min_length} > {max_length}.")
    if min_length is None and max_length is not None:
        min_length = max(1, max_length * 4 // 5)
    return min_length, max_length


def _distance_to_range(length: int, min_length: int | None, max_length: int | None) -> int:
    """Distance from *length* to the closed interval [*min_length*, *max_length*]; ``None`` bounds are open."""
    return max(
        0,
        min_length - length if min_length is not None else 0,
        length - max_length if max_length is not None else 0,
    )


def _render_summarize_prompt(
    raw: str, requirement: str, min_length: int | None, max_length: int | None, length_type: LengthType
) -> str:
    """Render the summarization prompt for *raw*."""
    return TEMPLATE_MANAGER.render_template(
        capabilities_config.summarize_template,
        {
            "text": raw,
            "requirement": requirement,
            "min_length": min_length,
            "max_length": max_length,
            "length_type": length_type.value,
        },
    )


class Summarize(Propose, ABC):
    """A class that provides functionality to summarize raw text into a length-bounded summary."""

    async def summarize(
        self,
        raw: str,
        max_length: PositiveInt | None = None,
        requirement: str = "",
        min_length: int | None = None,
        length_type: LengthType = LengthType.Chars,
        send_to: str | None = None,
        **kwargs: Unpack[LLMKwargs],
    ) -> str | None:
        """Summarize *raw* text into a summary whose length lands inside a [min, max] window.

        Both bounds ``None`` summarize without any length control; a set ceiling
        without a floor derives a floor of 80% of the ceiling.

        Args:
            raw: The raw text to be summarized.
            max_length: The upper bound of the summary length, in *length_type* units.
                ``None`` leaves the length unconstrained above.
            requirement: What must be preserved in the summary (key points, tone,
                language, etc.). Empty adds no requirement section to the prompt.
            min_length: The lower bound of the summary length, in *length_type*
                units. ``None`` derives ``max(1, max_length * 4 // 5)`` when
                *max_length* is set, and stays open otherwise.
            length_type: The unit used to measure the output length.
                Defaults to ``LengthType.Chars``.
            send_to: Routing-group variant for the LLM call; ``None`` defers to the
                role-level ``llm_send_to``, then the configured variant slots / global default.
            **kwargs (Unpack[LLMKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            The summary if its length falls inside the window, otherwise ``None``
            after the validation attempts are exhausted.
        """
        min_len, max_len = _resolve_bounds(min_length, max_length)

        def _validator(response: str) -> str | None:
            summary = response.strip()
            return summary if _distance_to_range(_length(summary, length_type), min_len, max_len) == 0 else None

        return await self.aask_validate(
            question=_render_summarize_prompt(raw, requirement, min_len, max_len, length_type),
            validator=_validator,
            send_to=send_to,
            **kwargs,
        )

    async def force_summarize(
        self,
        raw: str,
        max_length: PositiveInt | None = None,
        requirement: str = "",
        min_length: int | None = None,
        length_type: LengthType = LengthType.Chars,
        max_iterations: PositiveInt = 5,
        send_to: str | None = None,
        **kwargs: Unpack[LLMKwargs],
    ) -> str | None:
        """Summarize *raw* iteratively until the output lands inside the [min, max] window.

        An over-long attempt is fed back as the input of the next pass (shrinking
        toward the window); an under-min attempt restarts from the original *raw*.

        Args:
            raw: The raw text to be summarized.
            max_length: The upper bound of the summary length, in *length_type* units.
                ``None`` leaves the length unconstrained above.
            requirement: What must be preserved in the summary (key points, tone,
                language, etc.). Empty adds no requirement section to the prompt.
            min_length: The lower bound of the summary length, in *length_type*
                units. ``None`` derives ``max(1, max_length * 4 // 5)`` when
                *max_length* is set, and stays open otherwise.
            length_type: The unit used to measure the output length.
                Defaults to ``LengthType.Chars``.
            max_iterations: The maximum number of summarization passes.
                Defaults to 5.
            send_to: Routing-group variant for the LLM call; ``None`` defers to the
                role-level ``llm_send_to``, then the configured variant slots / global default.
            **kwargs (Unpack[LLMKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            The first output inside the length window, or the attempt whose length
            is closest to the window if the window could not be reached within
            *max_iterations*, or ``None`` if every pass failed.
        """
        min_len, max_len = _resolve_bounds(min_length, max_length)
        source = raw
        best: str | None = None
        for _ in range(max_iterations):
            candidate = await self.aask_validate(
                question=_render_summarize_prompt(source, requirement, min_len, max_len, length_type),
                validator=lambda response: response.strip() or None,
                send_to=send_to,
                **kwargs,
            )
            if candidate is None:
                break
            distance = _distance_to_range(_length(candidate, length_type), min_len, max_len)
            if distance == 0:
                return candidate
            if best is None or distance < _distance_to_range(_length(best, length_type), min_len, max_len):
                best = candidate
            source = candidate if max_len is not None and _length(candidate, length_type) > max_len else raw
        if best is not None:
            logger.warn(
                f"force_summarize could not reach the length window (min={min_len}, max={max_len} "
                f"{length_type.value}) within {max_iterations} iterations; returning the closest attempt."
            )
        return best
