"""This module contains the capabilities for the lancedb."""

import asyncio
from typing import Iterable, List, Self, Tuple, Type

from fabricatio_rag.capabilities.rag import RAG, RAGConfigBase
from more_itertools import flatten

from fabricatio_lancedb.inited_service import get_service
from fabricatio_lancedb.models.lancedb import LancedbDocumentModel


class LancedbAddRAGConfig(RAGConfigBase):
    """LanceDB-specific RAG configuration."""

    table_name: str | None = None


class LancedbFetchRAGConfig[D: LancedbDocumentModel](RAGConfigBase):
    """LanceDB-specific RAG configuration."""

    document_model: Type[D]
    limit: int = 15
    table_name: str | None = None


class LancedbRAG[D: LancedbDocumentModel, AC: LancedbAddRAGConfig, FC: LancedbFetchRAGConfig](RAG[D, D, AC, FC]):
    """LanceDB-specific RAG capability extending the base RAG class."""

    async def add_document(self, data: D | List[D], config: AC | None = None) -> Self:
        """Add a document to the LanceDB collection."""
        conf = config or LancedbAddRAGConfig.default()

        table = await (await get_service()).create_or_open_table(conf.table_name)

        data_seq = data if isinstance(data, list) else [data]
        vec_seq = await self.vectorize([d.prepare_vectorization() for d in data_seq])

        packs: Iterable[Tuple[D, List[float]]] = zip(data_seq, vec_seq, strict=True)

        await table.add_documents([d.prepare_insertion(v) for (d, v) in packs])

        return self

    async def afetch_document(self, query: str | List[str], config: FC | None = None) -> List[D]:
        """Fetch documents from the LanceDB collection."""
        conf = config or LancedbFetchRAGConfig.default()

        table = await (await get_service()).create_or_open_table(conf.table_name)

        if isinstance(query, str):
            search_vec = await self.vectorize(query)

            searched = await table.search_document(search_vec, limit=conf.limit)

            return [conf.document_model.from_raw(s) for s in searched]
        search_vec = await self.vectorize(query)
        searched: List[List[D]] = await asyncio.gather(
            *[table.search_document(v, limit=conf.limit) for v in search_vec]
        )
        return list(flatten(searched))
