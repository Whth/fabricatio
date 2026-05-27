"""Database storage actions for RAG document models."""

from abc import ABC
from pathlib import Path
from typing import Any, ClassVar, List, Type

from fabricatio_core import logger
from fabricatio_core.models.action import Action
from more_itertools.more import chunked

from fabricatio_rag.capabilities.rag import RAG, RAGConfigBase
from fabricatio_rag.models.document import SearchedDocumentModel, StoredDocumentModel


class StoreTextFile[STD: StoredDocumentModel, SRD: SearchedDocumentModel, AC: RAGConfigBase, FC: RAGConfigBase](
    Action, RAG[STD, SRD, AC, FC], ABC
):
    """Ingest text files, chunk them, and store in the vector database."""

    store_model: Type[STD]

    store_config: AC | None = None
    chunk_size: int = 512
    chunk_overlap_ratio: float = 0.3

    store_batch_size: int = 10
    ctx_override: ClassVar[bool] = True

    async def _execute(
        self,
        text_files: List[Path],
        *_: Any,
        **cxt,
    ) -> int:
        logger.debug(f"Chunking {len(text_files)} text file(s) into chunk sized {self.chunk_size}...")
        models = self.store_model.from_txt_files(text_files, self.chunk_size, self.chunk_overlap_ratio)
        logger.debug(f"Get {len(models)} chunks.")
        batches = list(chunked(models, self.store_batch_size))
        logger.debug(f"Store {len(batches)} batches.")
        for batch in batches:
            await self.add_document(batch, config=self.store_config)
        return len(text_files)


class StoreDocuments[STD: StoredDocumentModel, SRD: SearchedDocumentModel, AC: RAGConfigBase, FC: RAGConfigBase](
    Action, RAG[STD, SRD, AC, FC], ABC
):
    """Store pre-built document model instances directly into the vector database.

    Unlike StoreTextFile, this action does NOT ingest file paths or chunk text.
    The caller is responsible for constructing the model instances beforehand.
    """

    store_config: AC | None = None
    ctx_override: ClassVar[bool] = True

    async def _execute(self, documents: List[STD], *_: Any, **cxt) -> int:
        await self.add_document(documents, config=self.store_config)
        return len(documents)
