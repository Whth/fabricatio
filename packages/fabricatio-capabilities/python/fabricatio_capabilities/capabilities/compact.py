"""A module that provides a capability to compact raw text to a target length."""

import re
from abc import ABC
from enum import StrEnum, auto
from typing import Unpack

from fabricatio_core import TEMPLATE_MANAGER
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import TASK, split_sentence_bounds, word_count

from fabricatio_capabilities.config import capabilities_config

_SENTENCE_SPLIT = re.compile(r"[^.!?。！？]+(?:[.!?。！？]+|$)")


class LengthType(StrEnum):
    """Units for measuring text length."""

    Chars = auto()
    """Count individual characters."""

    Words = auto()
    """Count whitespace-separated words."""

    Sentences = auto()
    """Count sentences, split on ``.`` ``!`` ``?`` and their full-width variants."""


def _length(text: str, length_type: LengthType) -> int:
    """Count the length of *text* in the given unit."""
    match length_type:
        case LengthType.Chars:
            return len(text)
        case LengthType.Words:
            return word_count(text)
        case LengthType.Sentences:
            return len(split_sentence_bounds(text))


class Compact(Propose, ABC):
    """A class that provides functionality to compact raw text to a target length."""

    async def compact(
        self,
        raw: str,
        requirement: str,
        target_length: int,
        length_type: LengthType = LengthType.Chars,
        send_to: str | None = TASK,
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
            question=TEMPLATE_MANAGER.render_template(
                capabilities_config.compact_template,
                {
                    "text": raw,
                    "requirement": requirement,
                    "target_length": target_length,
                    "length_type": length_type,
                },
            ),
            validator=_validator,
            send_to=send_to,
            **kwargs,
        )
