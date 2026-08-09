from dataclasses import field
from typing import ClassVar, Type

from fabricatio_lancedb.capabilities.lancedb import LancedbAddRAGConfig, LancedbFetchRAGConfig
from fabricatio_lancedb.models.lancedb import LancedbDocumentModel
from fabricatio_lancedb.rust import SearchedDocument, StoreDocument

from fabricatio_novel.config import novel_config


class WritingStyleDocument(LancedbDocumentModel[StoreDocument, SearchedDocument]):
    """Semantic marker for writing style documents stored in LanceDB."""

    rendering_template: ClassVar[str] = novel_config.writing_style_as_prompt_template


class WritingStyleAddConfig(LancedbAddRAGConfig):
    """Add configuration for writing style documents."""

    table_name: str = field(default_factory=lambda: novel_config.writing_styles_table_name)


class WritingStyleFetchConfig(LancedbFetchRAGConfig[WritingStyleDocument]):
    """Fetch configuration for writing style documents."""

    document_model: Type[WritingStyleDocument] = WritingStyleDocument
    table_name: str = field(default_factory=lambda: novel_config.writing_styles_table_name)


class EnrichedDocument(LancedbDocumentModel[StoreDocument, SearchedDocument]):
    """Semantic marker for LLM-enriched reference chunks stored in LanceDB."""

    rendering_template: ClassVar[str] = novel_config.enriched_as_prompt_template


class EnrichedAddConfig(LancedbAddRAGConfig):
    """Add configuration for enriched documents."""

    table_name: str = field(default_factory=lambda: novel_config.enriched_table_name)


class EnrichedFetchConfig(LancedbFetchRAGConfig[EnrichedDocument]):
    """Fetch configuration for enriched documents."""

    document_model: Type[EnrichedDocument] = EnrichedDocument
    table_name: str = field(default_factory=lambda: novel_config.enriched_table_name)
