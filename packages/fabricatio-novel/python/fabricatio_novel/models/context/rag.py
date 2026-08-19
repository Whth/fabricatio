"""RAG retrieval settings and story-scoped style references carried down the context tree."""

from typing import Self

from pydantic import Field

from fabricatio_novel.models.rag import WritingStyleDocument


class RAGChannel:
    """Caller-owned RAG retrieval settings and story-scoped style references."""

    rag_query: str = ""
    """Additional query guideline for style retrieval; combined with the story description."""

    rag_limit: int = 15
    """Reference documents kept for the story's scene prompts.

    The story description query retrieves this limit of documents.
    """

    style_docs: list[WritingStyleDocument] = Field(default_factory=list)
    """Writing style reference documents retrieved for this story; injected raw into its scenes."""

    def set_rag_query(self, query: str) -> Self:
        """Set the additional retrieval query guideline."""
        self.rag_query = query
        return self

    def set_rag_limit(self, limit: int) -> Self:
        """Set the reference documents kept for the story's scene prompts."""
        self.rag_limit = limit
        return self

    def set_style_docs(self, docs: list[WritingStyleDocument]) -> Self:
        """Set the retrieved writing style references and return self."""
        self.style_docs = docs
        return self
