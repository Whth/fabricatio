"""RAG-bound context variants: retrieval settings sealed onto a dedicated story subclass."""

from typing import Self

from fabricatio_core.utils import wrap_in_block
from pydantic import BaseModel, Field

from fabricatio_novel.models.context.log import ContextEntry
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

    The story-planning stage seals plain story contexts into this subclass and
    houses them in a :class:`~fabricatio_novel.models.context.chapter.RagChapterContext`;
    every retrieval consumer types against this class, and the base
    :class:`~fabricatio_novel.models.context.story.StoryContext` stays free of
    retrieval state. Retrieved reference documents are held on
    ``retrieved_styles`` and render through :meth:`prefixed_header_entry` as one
    story-scoped entry shared by every scene write prompt's prefix-cacheable
    region; they never enter ``writing_styles``.
    """

    rag: RagRetrieval
    """Retrieval settings for this story's writing style references; required, so a plain story's snapshot never validates as this class."""

    retrieved_styles: list[str] = Field(default_factory=list)
    """Writing style reference texts retrieved for this story; rendered as one story-scoped prefix entry shared by every scene."""

    def add_retrieved_styles(self, styles: list[str]) -> Self:
        """Append non-empty retrieved style texts and return self."""
        self.retrieved_styles.extend(style for style in styles if style)
        return self

    def prefixed_header_entry(self) -> ContextEntry | None:
        """The retrieved style references as one entry seeded into every scene's prefix."""
        if not self.retrieved_styles:
            return None
        return ContextEntry(
            kind="style_references",
            title="Writing Style References",
            body=wrap_in_block(
                "Before writing this segment(s), i have retrieved some docs below, which you can refer to make the novel better"
                + "\n".join(self.retrieved_styles),
                title="Retried Writing Style References",
            ),
        )

    @classmethod
    def seal(cls, story: StoryContext, rag: RagRetrieval) -> "RagStoryContext":
        """Rebind a plain story context as RAG-bound, carrying the given settings.

        The rebind copies every field off the plain context's instance state — the
        dump-excluded run-wide constants (outline, language) included — so the
        roster's character state cards travel without being listed here, and so
        does any field added to a context base later. Only ``rag``, absent from
        the plain class, is applied on top; the key is required on this class,
        which is how snapshot loaders tell sealed trees from plain ones by
        validation alone.

        Sealing an already sealed story returns it unchanged.
        """
        if isinstance(story, RagStoryContext):
            return story

        return cls.model_validate({**vars(story), "rag": rag})
