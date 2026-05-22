from __future__ import annotations

"""Keyword argument types for novel RAG operations."""

from typing import TYPE_CHECKING, Optional

from fabricatio_core.models.kwargs_types import ValidateKwargs

if TYPE_CHECKING:
    from fabricatio_novel.capabilities.novel_rag import WritingStyleFetchConfig


class NovelRAGKwargs[T](ValidateKwargs[T], total=False):
    """Arguments for novel RAG chapter generation.

    Extends ValidateKwargs with writing style retrieval configuration.
    """

    writing_style_fetch_config: Optional[WritingStyleFetchConfig]
