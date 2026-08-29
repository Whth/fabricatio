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


def _resolve_min_length(min_length: int | None, max_length: int) -> int:
    """Resolve the effective lower length bound.

    ``None`` derives a floor of 80% of *max_length* (integer floor, at least 1) so a
    fixed-width display box never receives an overly short caption by default.
    """
    if min_length is None:
        return max(1, max_length * 4 // 5)
    if not 1 <= min_length <= max_length:
        raise ValueError(f"min_length must be within [1, {max_length}], got {min_length}.")
    return min_length


def _distance_to_range(length: int, min_length: int, max_length: int) -> int:
    """Distance from *length* to the closed interval [*min_length*, *max_length*]."""
    return max(0, min_length - length, length - max_length)


def _render_summarize_prompt(
    raw: str, requirement: str, min_length: int, max_length: int, length_type: LengthType
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
        max_length: PositiveInt,
        requirement: str = "",
        min_length: int | None = None,
        length_type: LengthType = LengthType.Chars,
        send_to: str | None = None,
        **kwargs: Unpack[LLMKwargs],
    ) -> str | None:
        """Summarize *raw* text into a summary whose length lands inside a [min, max] window.

        Args:
            raw: The raw text to be summarized.
            max_length: The upper bound of the summary length, in *length_type* units.
            requirement: What must be preserved in the summary (key points, tone,
                language, etc.). Empty adds no requirement section to the prompt.
            min_length: The lower bound of the summary length, in *length_type*
                units. ``None`` (default) derives ``max(1, max_length * 4 // 5)``.
            length_type: The unit used to measure the output length.
                Defaults to ``LengthType.Chars``.
            send_to: Routing-group variant for the LLM call; ``None`` defers to the
                role-level ``llm_send_to``, then the configured variant slots / global default.
            **kwargs (Unpack[LLMKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            The summary if its length falls within the window, otherwise ``None``
            after the validation attempts are exhausted.
        """
        min_len = _resolve_min_length(min_length, max_length)

        def _validator(response: str) -> str | None:
            summary = response.strip()
            return summary if _distance_to_range(_length(summary, length_type), min_len, max_length) == 0 else None

        return await self.aask_validate(
            question=_render_summarize_prompt(raw, requirement, min_len, max_length, length_type),
            validator=_validator,
            send_to=send_to,
            **kwargs,
        )

    async def force_summarize(
        self,
        raw: str,
        max_length: PositiveInt,
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
            requirement: What must be preserved in the summary (key points, tone,
                language, etc.). Empty adds no requirement section to the prompt.
            min_length: The lower bound of the summary length, in *length_type*
                units. ``None`` (default) derives ``max(1, max_length * 4 // 5)``.
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
        min_len = _resolve_min_length(min_length, max_length)
        source = raw
        best: str | None = None
        for _ in range(max_iterations):
            candidate = await self.aask_validate(
                question=_render_summarize_prompt(source, requirement, min_len, max_length, length_type),
                validator=lambda response: response.strip() or None,
                send_to=send_to,
                **kwargs,
            )
            if candidate is None:
                break
            distance = _distance_to_range(_length(candidate, length_type), min_len, max_length)
            if distance == 0:
                return candidate
            if best is None or distance < _distance_to_range(_length(best, length_type), min_len, max_length):
                best = candidate
            source = candidate if _length(candidate, length_type) > max_length else raw
        if best is not None:
            logger.warn(
                f"force_summarize could not reach the [{min_len}, {max_length}] {length_type.value} window within "
                f"{max_iterations} iterations; returning the closest attempt."
            )
        return best
