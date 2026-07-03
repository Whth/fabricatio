"""Writing style fetching document models."""

from typing import ClassVar, Type

from fabricatio_lancedb.capabilities.lancedb import LancedbAddRAGConfig, LancedbFetchRAGConfig
from fabricatio_lancedb.models.lancedb import LancedbDocumentModel
from fabricatio_lancedb.rust import SearchedDocument, StoreDocument

from fabricatio_novel.config import novel_config


class WritingStyleDocument(LancedbDocumentModel[StoreDocument, SearchedDocument]):
    """Semantic marker for writing style documents stored in LanceDB."""

    rendering_template: ClassVar[str] = novel_config.writing_style_as_prompt_template


class WritingStyleFetchConfig(LancedbFetchRAGConfig[WritingStyleDocument]):
    """Fetch configuration for writing style documents."""

    document_model: Type[WritingStyleDocument] = WritingStyleDocument
    use_refined_query: bool = False
    """When True, the user-supplied `writing_style_query` is refined by the LLM into multiple
    semantically-diverse queries before retrieval, and all variants are searched.
    Refinement is skipped when no `writing_style_query` is provided (falls back to the
    default script/scene-derived query)."""
    refined_query_count: int = 3
    """Number of refined query variants to produce when `use_refined_query` is True.
    Higher counts increase retrieval coverage at the cost of one extra embedding call
    per variant."""
    refine_query_template: str = novel_config.refined_query_template
    """Template name used by `RAG.arefined_query` to expand the raw user query into
    multiple semantically-diverse queries. Override to use a project-specific template."""


class WritingStyleAddConfig(LancedbAddRAGConfig):
    """Fetch configuration for writing style documents."""
