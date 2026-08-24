"""Semantic chunking capability using LLM-guided split-point indices.

Splits each input text into mini-chunks of roughly ``rag_config.mini_chunk_size``
characters, asks the LLM to emit the starting mini-chunk index of each output
chunk, then merges mini-chunks by those indices. Supports both single-string
and batch (list of strings) input.
"""

from typing import cast, overload

from fabricatio_core.capabilities.usages import UseLLM
from fabricatio_core.rust import TASK, TEMPLATE_MANAGER, split_into_chunks

from fabricatio_rag.config import rag_config


def normalize_splits(
    splits_seq: "list[int] | list[list[int]] | None",
    expected_len: int,
) -> "list[list[int] | None]":
    """Reconcile :meth:`UseLLM.alist_v`'s shape-polymorphic return with the batch length.

    Single-text calls yield ``list[int] | None``; batch calls yield
    ``list[list[int]]``.  Either way the result here is one entry per input text.
    """
    if splits_seq is None:
        return [None] * expected_len
    if expected_len == 1:
        return [cast("list[int]", splits_seq)]
    return cast("list[list[int] | None]", splits_seq)


def merge_mini_chunks(mini_chunks: "list[str]", splits: "list[int] | None") -> "list[str]":
    """Merge mini-chunks into output chunks at the given start indices.

    Each index in *splits* is the mini-chunk where a new output chunk begins.
    Out-of-bounds indices are skipped.  Fallbacks: no usable splits (``None``,
    empty, or all out-of-bounds) yields the whole text as one chunk; empty input
    yields no chunks.
    """
    if not splits or not mini_chunks:
        merged = "".join(mini_chunks)
        return [merged] if merged else []

    chunks: list[str] = []
    for i, start in enumerate(splits):
        if start >= len(mini_chunks):
            continue  # skip out-of-bounds split index
        end = splits[i + 1] if i + 1 < len(splits) else len(mini_chunks)
        chunks.append("".join(mini_chunks[start:end]))

    return chunks or ["".join(mini_chunks)]


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
        send_to: str | None = TASK,
    ) -> list[str]: ...
    @overload
    async def precise_chunk(
        self,
        chunk_guideline: str,
        text: list[str],
        max_size: int = 5,
        min_size: int = 2,
        mini_chunk_size: int | None = None,
        send_to: str | None = TASK,
    ) -> list[list[str]]: ...

    @overload
    async def precise_chunk(
        self,
        chunk_guideline: str,
        text: list[str] | str,
        max_size: int = 5,
        min_size: int = 2,
        mini_chunk_size: int | None = None,
        send_to: str | None = TASK,
    ) -> list[list[str]] | list[str]: ...

    async def precise_chunk(
        self,
        chunk_guideline: str,
        text: str | list[str],
        max_size: int = 5,
        min_size: int = 2,
        mini_chunk_size: int | None = None,
        send_to: str | None = TASK,
    ) -> list[str] | list[list[str]]:
        """Split text into semantically coherent chunks using LLM-guided split points.

        Args:
            chunk_guideline: Natural-language instruction for how to chunk.
            text: Single text or list of texts to chunk.
            max_size: Maximum mini-chunks per output chunk.
            min_size: Minimum mini-chunks per output chunk.
            mini_chunk_size: Character size of mini-chunks (defaults to rag_config.mini_chunk_size).
            send_to: Routing-group variant for the LLM call (defaults to TASK).

        Returns:
            For a single str: list of chunk strings.
            For a list of str: list of chunk-lists (one per input text).
        """
        m_chunk_size = mini_chunk_size or rag_config.mini_chunk_size

        was_str = isinstance(text, str)
        texts: list[str] = [text] if was_str else [*text]

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
        splits_seq = cast(
            "list[int] | list[list[int]] | None",
            await self.alist_v(rendered, int, send_to=send_to),
        )

        # Phase 5 + 6: normalize the LLM's shape-polymorphic return, then merge
        final_chunks = [
            merge_mini_chunks(mini, splits)
            for mini, splits in zip(para_seq, normalize_splits(splits_seq, len(para_seq)), strict=True)
        ]

        return final_chunks[0] if was_str else final_chunks
