"""Pipeline channel model for a chapter: its plan and the story contexts it writes."""

from collections.abc import Generator
from itertools import count
from typing import ClassVar, final

from fabricatio_novel.models.context.base import ParentContextBase
from fabricatio_novel.models.context.log import ContextEntry
from fabricatio_novel.models.context.rag import RagStoryContext
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.plan import ChapterPlan


class ChapterContext[S: StoryContext, P: ChapterPlan](ParentContextBase[S, P]):
    """A chapter's composition channel: its plan, story contexts and heading block."""

    heading_level: ClassVar[str] = "#"

    @final
    def iter_story_content(self) -> Generator[str, None, None]:
        """Yield each story's composed content, in chapter order."""
        for story_ctx in self.child_contexts:
            yield from story_ctx.iter_scene_content()

    @final
    def iter_scenes(self) -> Generator[tuple[int, StoryContext, SceneContext], None, None]:
        """Yield every scene in prefix order as ``(scene_index, story, scene)``; indices are 1-based, chapter-scoped, and continuous across stories."""
        counter = count(1)
        for story in self.iter_prefixed_contexts():
            for scene in story.iter_prefixed_contexts():
                yield next(counter), story, scene

    @final
    def render_prefixed_header(self) -> str:
        """Render the chapter's heading block, seeded into each story's prefix.

        Only the title is emitted: the chapter description is a whole-chapter
        synopsis, and seeding it into every descendant prefix hands each scene
        writer the beats of the scenes that follow it.
        """
        return f"{self.heading_level} {self.title}"

    @final
    def prefixed_header_entry(self) -> ContextEntry:
        """Wrap the heading block as the header entry seeded into children's prefixes."""
        return ContextEntry(kind="chapter_header", title=self.title, body=self.render_prefixed_header())

    @final
    def prefixed_entries(self) -> tuple[ContextEntry, ...]:
        """Contribute the heading entry followed by the stories' entries."""
        entries: list[ContextEntry] = [self.prefixed_header_entry()]
        for child in self.iter_child_contexts():
            entries.extend(child.prefixed_entries())
        return tuple(entries)


class RagChapterContext(ChapterContext[RagStoryContext, ChapterPlan]):
    """A chapter whose stories are all RAG-sealed: children are type-constrained.

    :class:`RagStoryContext` requires its ``rag`` settings, so reloading a
    persisted chapter into this class restores every sealed story — retrieval
    state included — by pydantic validation alone, with no per-item repair.
    """
