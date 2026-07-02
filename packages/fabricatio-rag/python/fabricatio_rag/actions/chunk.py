"""Semantic chunking actions using LLM-guided split points."""

from abc import ABC
from typing import Any, ClassVar

from fabricatio_core.models.action import Action

from fabricatio_rag.capabilities.chunk import PreciseChunkText


class ChunkAction(Action, PreciseChunkText, ABC):
    """Split text into semantically coherent chunks using LLM-guided split points."""

    ctx_override: ClassVar[bool] = True

    async def _execute(
        self,
        chunk_guideline: str,
        text: str | list[str],
        max_size: int = 5,
        min_size: int = 2,
        mini_chunk_size: int | None = None,
        *_: Any,
        **cxt,
    ) -> list[str] | list[list[str]]:
        return await self.precise_chunk(chunk_guideline, text, max_size, min_size, mini_chunk_size)
