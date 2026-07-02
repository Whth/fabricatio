"""Semantic chunking capability using LLM-guided split-point indices.

Splits each input text into mini-chunks of roughly ``rag_config.mini_chunk_size``
characters, asks the LLM to emit the starting mini-chunk index of each output
chunk, then merges mini-chunks by those indices. Supports both single-string
and batch (list of strings) input.
"""

from typing import List, overload

from fabricatio_core.capabilities.usages import UseLLM
from fabricatio_core.rust import TEMPLATE_MANAGER, split_into_chunks

from fabricatio_rag.config import rag_config


class PreciseChunkText(UseLLM):
    """LLM-guided text chunker.

    Splits texts into semantically coherent chunks by combining a deterministic
    mini-chunker (Rust ``split_into_chunks``) with an LLM that emits the
    starting mini-chunk index of each output chunk.
    """

    @overload
    async def precise_chunk(
        self,
        chunk_guideline: str,
        text: str,
        max_size: int = 5,
        min_size: int = 2,
        mini_chunk_size: int | None = None,
    ) -> List[str]: ...
    @overload
    async def precise_chunk(
        self,
        chunk_guideline: str,
        text: List[str],
        max_size: int = 5,
        min_size: int = 2,
        mini_chunk_size: int | None = None,
    ) -> List[List[str]]: ...

    @overload
    async def precise_chunk(
        self,
        chunk_guideline: str,
        text: List[str] | str,
        max_size: int = 5,
        min_size: int = 2,
        mini_chunk_size: int | None = None,
    ) -> List[List[str]] | List[str]: ...

    async def precise_chunk(
        self,
        chunk_guideline: str,
        text: str | List[str],
        max_size: int = 5,
        min_size: int = 2,
        mini_chunk_size: int | None = None,
    ) -> List[str] | List[List[str]]:
        """Split text into semantically coherent chunks using LLM-guided split points.

        Args:
            chunk_guideline: Natural-language instruction for how to chunk.
            text: Single text or list of texts to chunk.
            max_size: Maximum mini-chunks per output chunk.
            min_size: Minimum mini-chunks per output chunk.
            mini_chunk_size: Character size of mini-chunks (defaults to rag_config.mini_chunk_size).

        Returns:
            For a single str: list of chunk strings.
            For a list of str: list of chunk-lists (one per input text).
        """
        m_chunk_size = mini_chunk_size or rag_config.mini_chunk_size

        was_str = isinstance(text, str)
        texts = [text] if was_str else text

        # Phase 1: split each input text into mini-chunks (no overlap)
        para_seq: list[list[str]] = [split_into_chunks(s, m_chunk_size, max_overlapping_rate=0.0) for s in texts]

        # Phase 2: build template contexts — one per input text
        contexts = [
            {
                "guideline": chunk_guideline,
                "mini_chunks": mini_chunks,
                "max_size": max_size,
                "min_size": min_size,
            }
            for mini_chunks in para_seq
        ]

        # Phase 3: render templates (single dict → str, list of dicts → list[str])
        rendered = TEMPLATE_MANAGER.render_template(
            rag_config.precise_chunk_template,
            contexts if len(contexts) > 1 else contexts[0],
        )

        # Phase 4: LLM determines split-point indices
        # When len(para_seq)==1 → alist_v(str, int) → List[int] | None
        # When len(para_seq)>1  → alist_v(list[str], int) → List[List[int] | None] | None
        splits_seq = await self.alist_v(rendered, int)

        # Phase 5: normalize splits_seq to list[list[int] | None] matching para_seq length
        if splits_seq is None:
            normalized_splits: list[list[int] | None] = [None] * len(para_seq)
        elif len(para_seq) == 1:
            # Single-text path: alist_v returned List[int]; wrap for uniform iteration
            normalized_splits = [splits_seq]  # type: ignore[list-item]
        else:
            # Batch path: alist_v returned List[List[int] | None]
            normalized_splits = splits_seq  # type: ignore[assignment]

        # Phase 6: merge mini-chunks by split indices
        final_chunks: list[list[str]] = []
        for mini_chunks, splits in zip(para_seq, normalized_splits, strict=True):
            if not splits or len(mini_chunks) == 0:
                # Fallback: no splits or empty input → treat entire text as one chunk
                merged = "".join(mini_chunks)
                final_chunks.append([merged] if merged else [])
                continue

            merged: list[str] = []
            for i, start in enumerate(splits):
                if start >= len(mini_chunks):
                    continue  # skip out-of-bounds split index
                end = splits[i + 1] if i + 1 < len(splits) else len(mini_chunks)
                merged.append("".join(mini_chunks[start:end]))

            if not merged:
                merged = ["".join(mini_chunks)]  # all splits were out of bounds
            final_chunks.append(merged)

        return final_chunks[0] if was_str else final_chunks
