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

        Sealing an already sealed story returns it unchanged.
        """
        if isinstance(story, RagStoryContext):
            return story

        return (
            RagStoryContext.create(
                outline=story.outline,
                language=story.language,
            )
            .update_from(story.plan)
            .set_plan(story.plan)
            .set_writing_styles(story.writing_styles)
            .set_writing_constraints(story.writing_constraints)
            .set_rag(rag)
            .expect_(story.expected_word_count)
        )
