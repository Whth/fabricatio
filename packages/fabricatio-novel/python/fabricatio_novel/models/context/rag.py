"""RAG-bound context variants: retrieval settings sealed onto a dedicated story subclass."""

from typing import Self

from pydantic import BaseModel, Field

from fabricatio_novel.models.context.story import StoryContext


class RagRetrieval(BaseModel):
    """Caller-owned retrieval settings for story-bound writing style references.

    The settings live exclusively on :class:`RagStoryContext`; the standard
    context tree never carries them, so plain runs stay RAG-free.
    """

    query: str = ""
    """Additional query guideline for style retrieval; combined with the story description."""

    limit: int = 15
    """Reference documents kept for the story's scene prompts."""


class RagStoryContext(StoryContext):
    """A story context sealed with writing style retrieval settings.

    The RAG pipeline swaps plain story contexts for this subclass before their
    scenes are planned; every retrieval consumer types against this class, and
    the base :class:`~fabricatio_novel.models.context.story.StoryContext` stays
    free of retrieval state.
    """

    rag: RagRetrieval = Field(default_factory=RagRetrieval)
    """Retrieval settings for this story's writing style references."""

    def set_rag(self, rag: RagRetrieval) -> Self:
        """Set the retrieval settings and return self."""
        self.rag = rag
        return self

    @classmethod
    def seal(cls, story: StoryContext, rag: RagRetrieval) -> "RagStoryContext":
        """Rebind a plain story context as RAG-bound, carrying the given settings.

        The rebind reads every field off the plain context directly, so the roster's
        character state cards travel without being listed here — and so does any
        field added to a context base later. Only ``rag``, absent from the plain
        class, is applied on top.

        Sealing an already sealed story returns it unchanged.
        """
        if isinstance(story, RagStoryContext):
            return story

        return RagStoryContext.model_validate(story, from_attributes=True).set_rag(rag)
