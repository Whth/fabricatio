"""This module contains the capabilities for the lancedb."""

from typing import List, Self, Type

from fabricatio_rag.capabilities.rag import RAG, RAGConfigBase

from fabricatio_lancedb.models.lancedb import LancedbDocumentModel


class LancedbRAGConfig(RAGConfigBase):
    """LanceDB-specific RAG configuration."""

    collection_name: str | None = None


class LancedbRAG[D: LancedbDocumentModel, AC: LancedbRAGConfig, FC: LancedbRAGConfig](RAG[D, AC, FC]):
    """LanceDB-specific RAG capability extending the base RAG class."""

    async def add_document(self, data: D | List[D], config: AC | None = None) -> Self:
        raise NotImplementedError

    async def afetch_document(
        self, query: str | List[str], document_model: Type[D], config: FC | None = None
    ) -> List[D]:
        raise NotImplementedError
