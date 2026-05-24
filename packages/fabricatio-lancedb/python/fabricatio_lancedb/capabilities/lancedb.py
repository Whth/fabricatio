"""This module contains the capabilities for the lancedb."""

import asyncio
from typing import Iterable, List, Optional, Self, Tuple, Type

from fabricatio_core import CONFIG
from fabricatio_core.utils import first_available, ok
from fabricatio_rag.capabilities.rag import RAG, RAGConfigBase
from more_itertools import flatten
from pydantic import Field

from fabricatio_lancedb.inited_service import get_service
from fabricatio_lancedb.models.lancedb import LancedbDocumentModel


class LancedbAddRAGConfig(RAGConfigBase):
    """LanceDB-specific RAG configuration."""

    table_name: str | None = None


class LancedbFetchRAGConfig[D: LancedbDocumentModel](RAGConfigBase):
    """LanceDB-specific RAG configuration."""

    document_model: Optional[Type[D]] = None
    limit: int = 15
    table_name: str | None = None


class LancedbRAG[D: LancedbDocumentModel, AC: LancedbAddRAGConfig, FC: LancedbFetchRAGConfig](RAG[D, D, AC, FC]):
    """LanceDB-specific RAG capability extending the base RAG class."""

    target_table: Optional[str] = Field(default=None)
    """The name of the table being viewed."""

    def view(self, table_name: Optional[str]) -> Self:
        """View the specified table."""
        self.target_table = table_name
        return self

    def quit_viewing(self) -> Self:
        """Quit the current view."""
        return self.view(None)

    @property
    def safe_target_table(self) -> str:
        """Get the name of the table being viewed."""
        return ok(self.target_table, "No table is being viewed. Have you called `self.view()`?")

    async def add_document(self, data: D | List[D], config: AC | None = None) -> Self:
        """Add a document to the LanceDB collection."""
        conf = config or LancedbAddRAGConfig.default()

        table = await (await get_service()).create_or_open_table(
            conf.table_name or self.safe_target_table,
            first_available((self.embedding_ndim, CONFIG.embedding.ndim)),
        )

        data_seq = data if isinstance(data, list) else [data]
        vec_seq = await self.vectorize([d.prepare_vectorization() for d in data_seq])

        packs: Iterable[Tuple[D, List[float]]] = zip(data_seq, vec_seq, strict=True)

        await table.add_documents([d.prepare_insertion(v) for (d, v) in packs])

        return self

    async def afetch_document(self, query: str | List[str], config: FC | None = None) -> List[D]:
        """Fetch documents from the LanceDB collection."""
        conf = config or LancedbFetchRAGConfig.default()
        doc_model = conf.document_model
        if doc_model is None:
            raise ValueError("document_model must be provided in FetchConfig")

        table = await (await get_service()).open_table(conf.table_name or self.safe_target_table)

        if isinstance(query, str):
            search_vec = await self.vectorize(query)
            searched = await table.search_document(search_vec, limit=conf.limit)
            return [doc_model.from_raw(s) for s in searched]

        search_vec = await self.vectorize(query)
        searched: List[List[D]] = await asyncio.gather(
            *[table.search_document(v, limit=conf.limit) for v in search_vec]
        )
        return list(flatten(searched))

    async def aretrieve(
        self,
        query: str | List[str],
        document_model: Type[D],
        max_accepted: int = 10,
        table_name: Optional[str] = None,
        result_per_query: Optional[int] = None,
    ) -> List[D]:
        """Convenience method to vectorize a query, search LanceDB, and return typed documents.

        Args:
            query: The query string(s) to search for.
            document_model: The LancedbDocumentModel subclass to deserialize results into.
            max_accepted: Maximum number of results to return.
            table_name: Override the target table name.
            result_per_query: If provided, overrides max_accepted for the limit.

        Returns:
            List of document instances of type D.
        """
        conf = LancedbFetchRAGConfig(
            document_model=document_model,
            limit=result_per_query or max_accepted,
            table_name=table_name,
        )
        return await self.afetch_document(query, conf)
