"""Action for storing LLM-enriched text chunks in the LanceDB vector store.

Mirrors `StoreWritingStyleTexts`: reads text files, processes them, and
indexes the resulting documents under a dedicated LanceDB table. Here the
processing step is `EnrichChunkTextNovel.enrich`, which produces
question-answer pairs from each source file. Each pair is flattened into a
short text string and stored as one `EnrichedDocument`.
"""

from abc import ABC
from pathlib import Path
from typing import Any, ClassVar, Iterable, List, Optional

from fabricatio_core import Action, logger
from fabricatio_lancedb.capabilities.lancedb import LancedbRAG
from fabricatio_rag.capabilities.chunk import PreciseChunkText
from fabricatio_rag.models.qa import QAPair

from fabricatio_novel.capabilities.enrich import EnrichChunkTextNovel
from fabricatio_novel.models.novel_enrich import (
    EnrichedAddConfig,
    EnrichedDocument,
    EnrichedFetchConfig,
)


class EnrichedNovelComposeRAG(
    EnrichChunkTextNovel,
    PreciseChunkText,
    LancedbRAG[EnrichedDocument, EnrichedAddConfig, EnrichedFetchConfig],
    ABC,
):
    """MRO anchor combining enrichment, semantic chunking, and LanceDB storage.

    Pulls together:
    - `EnrichChunkTextNovel.enrich` for QA-pair generation per chunk
    - `PreciseChunkText.precise_chunk` for LLM-guided semantic splitting of source files
      (each input file is split into coherent chunks before enrichment, since naive
      whole-file enrichment degrades on long texts)
    - `LancedbRAG` for `add_document` / `rebuild_index` machinery over `EnrichedDocument`
    """


def _qa_pairs_to_chunks(qa_pairs: Iterable[QAPair]) -> List[str]:
    """Flatten `EnrichmentResult.qa_pairs` into one text per pair."""
    return [f"Question: {pair.question}\nAnswer: {pair.answer}" for pair in qa_pairs]


class StoreEnrichedTexts(Action, EnrichedNovelComposeRAG, ABC):
    """Store LLM-enriched text chunks from files into LanceDB.

    Each input file is read, semantically split into coherent chunks via
    `PreciseChunkText.precise_chunk`, fed chunk-by-chunk to
    `EnrichChunkTextNovel.enrich` to produce question-answer pairs, and each
    pair is indexed as a separate `EnrichedDocument`. Document count is stored
    under `output_key` (default `"stored_count"`).
    """

    enrich_guideline: str = ""
    """Guidance passed to `EnrichChunkTextNovel.enrich` for QA generation."""

    chunk_guideline: str = ""
    """Guidance passed to `PreciseChunkText.precise_chunk` for semantic splitting."""

    text_files: Optional[List[Path]] = None
    """Files to read, chunk, enrich, and store. Provided by the workflow runtime."""

    output_key: str = "stored_count"
    """Key under which the number of stored documents is stored in context."""

    store_config: Optional[EnrichedAddConfig] = None
    """Optional LanceDB add-config override (table_name, batch sizes, rebuild flag)."""

    chunk_max_size: int = 5
    """Maximum mini-chunks per output chunk (passed to `precise_chunk`)."""

    chunk_min_size: int = 2
    """Minimum mini-chunks per output chunk (passed to `precise_chunk`)."""

    mini_chunk_size: Optional[int] = None
    """Mini-chunk character size override (defaults to `rag_config.mini_chunk_size`)."""

    ctx_override: ClassVar[bool] = True

    async def _execute(self, *_: Any, **cxt: Any) -> int:
        """Read files, chunk semantically, enrich chunks, store QA pairs in LanceDB."""
        files = self.text_files or []
        if not files:
            logger.warn("No text files provided to StoreEnrichedTexts; nothing to store.")
            return 0

        texts = [f.read_text(encoding="utf-8") for f in files]

        # Phase 1: semantic chunking via LLM-guided split points.
        # precise_chunk returns List[List[str]] (one chunk-list per input text).
        per_file_chunks = await self.precise_chunk(
            self.chunk_guideline,
            texts,
            max_size=self.chunk_max_size,
            min_size=self.chunk_min_size,
            mini_chunk_size=self.mini_chunk_size,
        )
        flat_chunks: List[str] = [c for chunks in per_file_chunks for c in chunks if c.strip()]
        if not flat_chunks:
            logger.warn("Precise chunking produced no chunks; nothing to enrich.")
            return 0

        # Phase 2: enrich each chunk into QA pairs.
        results = await self.enrich(self.enrich_guideline, flat_chunks)
        chunks: List[str] = [c for r in results for c in _qa_pairs_to_chunks(r.qa_pairs)]
        if not chunks:
            logger.warn("Enrichment produced no QA pairs; nothing to store.")
            return 0

        # Phase 3: index QA-pair texts as EnrichedDocument rows.
        models = [EnrichedDocument.with_text_chunk(c) for c in chunks]
        await self.add_document(models, config=self.store_config)

        table_name = self.store_config.table_name if self.store_config else None
        await self.rebuild_index(table_name)
        logger.info(
            f"Stored {len(models)} enriched QA chunk(s) from "
            f"{len(flat_chunks)} source chunk(s) across {len(files)} file(s)."
        )
        return len(models)
