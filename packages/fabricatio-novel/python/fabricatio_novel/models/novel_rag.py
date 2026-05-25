"""Writing style fetching document models."""

from typing import Type

from fabricatio_lancedb.capabilities.lancedb import LancedbAddRAGConfig, LancedbFetchRAGConfig
from fabricatio_lancedb.models.lancedb import LancedbDocumentModel
from fabricatio_lancedb.rust import SearchedDocument, StoreDocument


class WritingStyleDocument(LancedbDocumentModel[StoreDocument, SearchedDocument]):
    """Semantic marker for writing style documents stored in LanceDB."""


class WritingStyleFetchConfig(LancedbFetchRAGConfig[WritingStyleDocument]):
    """Fetch configuration for writing style documents."""

    document_model: Type[WritingStyleDocument] = WritingStyleDocument


class WritingStyleAddConfig(LancedbAddRAGConfig):
    """Fetch configuration for writing style documents."""
