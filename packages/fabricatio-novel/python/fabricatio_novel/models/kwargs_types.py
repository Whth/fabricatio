"""Keyword argument types for novel RAG operations."""

from typing import Optional

from fabricatio_core.models.kwargs_types import ValidateKwargs

from fabricatio_novel.models.novel_rag import WritingStyleFetchConfig


class NovelRAGKwargs[T](ValidateKwargs[T], total=False):
    """Arguments for novel RAG chapter generation.

    Extends ValidateKwargs with writing style retrieval configuration and optional
    query refinement.
    """

    writing_style_fetch_config: Optional[WritingStyleFetchConfig]
    use_reranker: bool
    writing_style_query: Optional[str]
    """Raw user-supplied writing-style intent (e.g. "Hemingway terse prose style").
    When `WritingStyleFetchConfig.use_refined_query` is True, this is refined by the LLM
    into multiple semantically-diverse queries before LanceDB retrieval. When falsy,
    retrieval falls back to the script/scene-derived query. Config fields
    (`use_refined_query`, `refined_query_count`, `refine_query_template`) belong on the
    `WritingStyleFetchConfig` itself, not as kwargs here."""
