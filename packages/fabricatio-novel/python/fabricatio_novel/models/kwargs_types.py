"""Keyword argument types for novel RAG operations."""

from typing import Optional

from fabricatio_core.models.kwargs_types import ValidateKwargs

from fabricatio_novel.models.novel_rag import WritingStyleFetchConfig


class NovelRAGKwargs[T](ValidateKwargs[T], total=False):
    """Arguments for novel RAG chapter generation.

    Extends ValidateKwargs with writing style retrieval configuration.
    """

    writing_style_fetch_config: Optional[WritingStyleFetchConfig]
