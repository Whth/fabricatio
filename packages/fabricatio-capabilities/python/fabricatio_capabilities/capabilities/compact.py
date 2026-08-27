"""A module that provides capabilities to compact raw text to a target length."""

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


def _render_compact_prompt(raw: str, requirement: str, target_length: int, length_type: LengthType) -> str:
    """Render the compaction prompt for *raw*."""
    return TEMPLATE_MANAGER.render_template(
        capabilities_config.compact_template,
        {
            "text": raw,
            "requirement": requirement,
            "target_length": target_length,
            "length_type": length_type.value,
        },
    )


class Compact(Propose, ABC):
    """A class that provides functionality to compact raw text to a target length."""

    async def compact(
        self,
        raw: str,
        requirement: str,
        target_length: int,
        length_type: LengthType = LengthType.Chars,
        send_to: str | None = None,
        **kwargs: Unpack[LLMKwargs],
    ) -> str | None:
        """Compact *raw* text to at most *target_length* units while preserving its core meaning.

        Args:
            raw: The raw text to be compacted.
            requirement: What must be preserved in the compacted output
                (key points, tone, language, etc.).
            target_length: The maximum length of the compacted output,
                measured in *length_type* units.
            length_type: The unit used to measure the output length.
                Defaults to ``LengthType.Chars``.
            send_to: Routing-group variant for the LLM call; ``None`` defers to the
                role-level ``llm_send_to``, then the configured variant slots / global default.
            **kwargs (Unpack[LLMKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            The compacted text if it satisfies the length constraint, otherwise ``None``
            after the validation attempts are exhausted.
        """

        def _validator(response: str) -> str | None:
            compacted = response.strip()
            return compacted if _length(compacted, length_type) <= target_length else None

        return await self.aask_validate(
            question=_render_compact_prompt(raw, requirement, target_length, length_type),
            validator=_validator,
            send_to=send_to,
            **kwargs,
        )

    async def force_compact(
        self,
        raw: str,
        requirement: str,
        target_length: int,
        length_type: LengthType = LengthType.Chars,
        max_iterations: PositiveInt = 5,
        send_to: str | None = None,
        **kwargs: Unpack[LLMKwargs],
    ) -> str | None:
        """Compact *raw* iteratively until the output fits within *target_length* units.

        Each pass compacts the previous output, so an oversized response is fed
        back as the input of the next pass instead of failing outright — a single
        LLM miss does not waste the run.

        Args:
            raw: The raw text to be compacted.
            requirement: What must be preserved in the compacted output
                (key points, tone, language, etc.).
            target_length: The maximum length of the compacted output,
                measured in *length_type* units.
            length_type: The unit used to measure the output length.
                Defaults to ``LengthType.Chars``.
            max_iterations: The maximum number of compaction passes.
                Defaults to 5.
            send_to: Routing-group variant for the LLM call; ``None`` defers to the
                role-level ``llm_send_to``, then the configured variant slots / global default.
            **kwargs (Unpack[LLMKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            The first output within the length bound, or the shortest output seen
            if the bound could not be met within *max_iterations*, or ``None`` if
            every pass failed.
        """
        current = raw
        best: str | None = None
        for _ in range(max_iterations):
            current = await self.aask_validate(
                question=_render_compact_prompt(current, requirement, target_length, length_type),
                validator=lambda response: response.strip() or None,
                send_to=send_to,
                **kwargs,
            )
            if current is None:
                break
            if best is None or _length(current, length_type) < _length(best, length_type):
                best = current
            if _length(current, length_type) <= target_length:
                return current
        if best is not None:
            logger.warn(
                f"force_compact could not meet the {target_length} {length_type.value} bound within "
                f"{max_iterations} iterations; returning the shortest attempt."
            )
        return best
