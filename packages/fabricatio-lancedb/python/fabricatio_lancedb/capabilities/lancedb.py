"""This module contains the capabilities for the lancedb."""

import asyncio
from dataclasses import field
from typing import Iterable, List, Optional, Self, Tuple, Type

from fabricatio_core import CONFIG
from fabricatio_core.utils import first_available, ok
from fabricatio_rag.capabilities.rag import RAG, RAGConfigBase
from more_itertools import chunked, flatten

from fabricatio_lancedb.config import lancedb_config
from fabricatio_lancedb.inited_service import get_service
from fabricatio_lancedb.models.lancedb import LancedbDocumentModel


class LancedbAddRAGConfig(RAGConfigBase):
    """LanceDB-specific RAG configuration."""

    table_name: str = field(default_factory=lambda: lancedb_config.default_table_name)
    embedding_batch_size: int = 10
    embedding_parallel_size: int = 10
    rebuild_index: bool = False


class LancedbFetchRAGConfig[D: LancedbDocumentModel](RAGConfigBase):
    """LanceDB-specific RAG configuration."""

    document_model: Optional[Type[D]] = None
    limit: int = 15
    table_name: str = field(default_factory=lambda: lancedb_config.default_table_name)


class LancedbRAG[D: LancedbDocumentModel, AC: LancedbAddRAGConfig, FC: LancedbFetchRAGConfig](RAG[D, D, AC, FC]):
    """LanceDB-specific RAG capability extending the base RAG class."""

    async def add_document(self, data: D | List[D], config: AC | None = None) -> Self:
        """Add a document to the LanceDB collection."""
        conf = config or LancedbAddRAGConfig.default()
        table = await (await get_service()).create_or_open_table(
            conf.table_name,
            first_available((self.embedding_ndim, CONFIG.embedding.ndim)),
        )

        data_seq = data if isinstance(data, list) else [data]
        batches = list(chunked(data_seq, conf.embedding_batch_size))
        sem = asyncio.Semaphore(conf.embedding_parallel_size)

        async def _worker(batch: list[D]) -> list[list[float]]:
            async with sem:
                return await self.vectorize([d.prepare_vectorization() for d in batch])

        vec_packs_seq: list[list[list[float]]] = await asyncio.gather(*[_worker(b) for b in batches])

        vec_seq = list(flatten(vec_packs_seq))

        packs: Iterable[Tuple[D, List[float]]] = zip(data_seq, vec_seq, strict=True)

        await table.add_documents([d.prepare_insertion(v) for (d, v) in packs], rebuild_index=conf.rebuild_index)

        return self

    async def afetch_document(self, query: str | List[str], config: FC | None = None) -> List[D]:
        """Fetch documents from the LanceDB collection."""
        conf = config or LancedbFetchRAGConfig.default()
        doc_model = ok(conf.document_model)
        table = await (await get_service()).open_table(conf.table_name)

        if isinstance(query, str):
            search_vec = await self.vectorize(query)
            searched = await table.search_document(search_vec, limit=conf.limit)
            return [doc_model.from_raw(s) for s in searched]

        search_vec = await self.vectorize(query)
        searched: List[List[D]] = await asyncio.gather(
            *[table.search_document(v, limit=conf.limit) for v in search_vec]
        )
        return list(flatten(searched))

    async def rebuild_index(self, table_name: str | None = None) -> Self:
        """Rebuild the index of the given table."""
        tbl_name = table_name or lancedb_config.default_table_name
        table = await (await get_service()).open_table(tbl_name)
        await table.rebuild_index()
        return self
