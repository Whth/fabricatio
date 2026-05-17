"""This module contains the capabilities for the lancedb."""

from abc import ABC

from fabricatio_rag.capabilities.rag import RAG, RAGConfigBase


class LancedbRAGConfig(RAGConfigBase):
    """LanceDB-specific RAG configuration."""

    collection_name: str | None = None


class LancedbRAG[D, AC: LancedbRAGConfig, FC: LancedbRAGConfig](RAG[D, AC, FC], ABC):
    """LanceDB-specific RAG capability extending the base RAG class."""
