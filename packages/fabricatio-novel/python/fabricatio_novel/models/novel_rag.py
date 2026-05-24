"""Writing style fetching document models."""

from typing import Type

from fabricatio_lancedb.capabilities.lancedb import LancedbFetchRAGConfig
from fabricatio_lancedb.models.lancedb import LancedbDocumentModel
from fabricatio_lancedb.rust import SearchedDocument, StoreDocument

from fabricatio_novel.config import novel_config


class WritingStyleDocument(LancedbDocumentModel[StoreDocument, SearchedDocument]):
    """Semantic marker for writing style documents stored in LanceDB."""


class WritingStyleFetchConfig(LancedbFetchRAGConfig[WritingStyleDocument]):
    """Fetch configuration for writing style documents."""

    document_model: Type[WritingStyleDocument] = WritingStyleDocument
    limit: int = 5
    table_name: str | None = novel_config.writing_styles_table_name
