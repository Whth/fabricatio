"""RAG-bound context levels: the retrieval settings and fetched references one level owns."""

from typing import Self

from fabricatio_core.utils import wrap_in_block
from pydantic import BaseModel, Field

from fabricatio_novel.models.context.log import ContextEntry, EntryKind
from fabricatio_novel.models.context.story import StoryContext


class RagRetrieval(BaseModel):
    """Caller-owned retrieval settings for one RAG-bound level's writing style references.

    Every RAG-bound level holds its own copy: the level takes the search text from
    its own channel (a story plans from its description, the novel root from the
    outline) and spends its own document budget. The standard context tree never
    carries them, so plain runs stay RAG-free.
    """

    query: str = ""
    """Additional query guideline for style retrieval, combined with the level's own text — a story's description, the novel's outline."""

    limit: int = 15
    """Reference documents kept for this level's prompts."""


class RagBound(BaseModel):
    """Retrieval state shared by every RAG-bound context level: the fetched references and how to read them.

    A level holds the texts it retrieved and answers the accessor its prompts read,
    so retrieval state lives on the context rather than in a parallel flag or a
    side channel.

    A concrete level MUST list this mixin before its context base —
    ``class RagStoryContext(RagBound, StoryContext)`` — because the plain tree
    answers :meth:`~fabricatio_novel.models.context.base.ContextBase.style_references`
    with an empty list, and only an earlier entry in the method resolution order
    outranks that default; listed second, the accessor would silently answer empty
    and the level's references would never render. ``test_novel_rag.py`` guards
    both RAG levels against a reordered base list.

    The retrieval settings themselves stay per level, because their requiredness
    differs: a sealed story requires its ``rag`` — that requirement is how a plain
    story's snapshot is told from a sealed one — while the run's root defaults it,
    so a snapshot written before the novel level retrieved anything still loads as
    the RAG root.
    """

    retrieved_styles: list[str] = Field(default_factory=list)
    """Writing style reference texts retrieved for this level, rendered only where the level needs them."""

    def add_retrieved_styles(self, styles: list[str]) -> Self:
        """Append non-empty retrieved style texts and return self."""
        self.retrieved_styles.extend(style for style in styles if style)
        return self

    def style_references(self) -> list[str]:
        """The writing style references this level retrieved."""
        return self.retrieved_styles


class RagStoryContext(RagBound, StoryContext):
    """A story context sealed with writing style retrieval settings.

    The story-planning stage seals plain story contexts into this subclass and
    houses them in a :class:`~fabricatio_novel.models.context.chapter.RagChapterContext`;
    every retrieval consumer types against this class, and the base
    :class:`~fabricatio_novel.models.context.story.StoryContext` stays free of
    retrieval state. Retrieved reference documents are held on
    ``retrieved_styles`` and render through :meth:`prefixed_header_entry` as one
    story-scoped entry shared by every scene write prompt's prefix-cacheable
    region; they never enter ``writing_styles``. Once every scene of the story
    carries content, :meth:`prefixed_header_entry` stops rendering them.
    """

    rag: RagRetrieval
    """Retrieval settings for this story's writing style references; required, so a plain story's snapshot never validates as this class."""

    def prefixed_header_entry(self) -> ContextEntry | None:
        """The retrieved style references as one entry seeded into every scene's prefix.

        Returns ``None`` once :meth:`~fabricatio_novel.models.context.story.StoryContext.is_fully_written`:
        the reference pile exists to steer this story's scene writes, so once they
        are written every later walk — the illustration proposals in particular —
        stops re-seeding it, and the raw texts stay on :attr:`retrieved_styles`
        for scoring and audit. The state is read off the prose itself rather than
        kept in a flag, because the prefix log is neither persisted nor stable:
        each walk re-derives the entry, so a tree rebuilt from a snapshot renders
        exactly what the run rendered.
        """
        if not self.style_references() or self.is_fully_written():
            return None
        return ContextEntry(
            kind=EntryKind.STYLE_REFERENCES,
            title="Writing Style References",
            body=wrap_in_block(
                "Before writing this segment(s), i have retrieved some docs below, which you can refer to make the novel better\n"
                + "\n".join(self.style_references()),
                title="Retrieved Writing Style References",
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
