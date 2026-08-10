"""RAG retrieval settings carried down the context tree to scenes."""

from typing import Self


class RAGChannel:
    """Caller-owned RAG retrieval settings, propagated to every scene context."""

    rag_query: str = ""
    """Additional query guideline for style retrieval; combined with the scene description."""

    rag_limit: int = 0
    """Reference documents retrieved per refined query; 0 uses the default configuration (15)."""

    def set_rag_query(self, query: str) -> Self:
        """Set the additional retrieval query guideline."""
        self.rag_query = query
        return self

    def set_rag_limit(self, limit: int) -> Self:
        """Set the per-refined-query retrieval limit (0 = default configuration)."""
        self.rag_limit = limit
        return self
