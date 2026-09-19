"""Pipeline channel model for the novel root: outline, language and chapter contexts."""

from collections.abc import Generator
from typing import Self, final

from pydantic import Field

from fabricatio_novel.models.context.base import ParentContextBase
from fabricatio_novel.models.context.chapter import ChapterContext, RagChapterContext
from fabricatio_novel.models.context.log import ContextEntry
from fabricatio_novel.models.context.rag import RagBound, RagRetrieval
from fabricatio_novel.models.plan import NovelPlan
from fabricatio_novel.models.series_book import SeriesBible


class NovelContext[C: ChapterContext, P: NovelPlan](ParentContextBase[C, P]):
    """The novel root channel: outline, language, plan and the chapter contexts it writes."""

    title: str = ""
    description: str = ""

    outline: str = ""
    language: str = ""
    series_bible: SeriesBible | None = None
    """The novel's setting bible; consumed at this root only — roster proposal and the
    seeded prefix entry that every descendant inherits through its prefix log."""

    @final
    def iter_chapter_content(self) -> Generator[str, None, None]:
        """Yield each chapter's composed content, in novel order."""
        for chapter_ctx in self.child_contexts:
            yield from chapter_ctx.iter_story_content()

    @final
    def prefixed_entries(self) -> tuple[ContextEntry, ...]:
        """Forward the chapters' entries; the novel's own title is not injected."""
        entries: list[ContextEntry] = []
        for child in self.iter_child_contexts():
            entries.extend(child.prefixed_entries())
        return tuple(entries)

    def set_series_bible(self, series_bible: SeriesBible | None) -> Self:
        """Set the novel's setting bible and return self."""
        self.series_bible = series_bible
        return self

    def seed_skill_prefix(self) -> Self:
        """Seed the run's skills as the leading entry of the running prefix.

        The skills are the user's own instructions for this novel, so they lead
        everything the run composes: each walk copies them into every
        descendant's prefix log, ahead of the setting bible. The entry carries
        the very bytes the planning and retrieval prompts lead with, so a run's
        calls to one model share that cached head. Idempotent: a run without
        skills seeds nothing and an existing entry is never duplicated.
        """
        if not self.skill_names:
            return self
        if any(entry.kind == "skills" for entry in self.prefix_log.entries):
            return self
        section = self.skill_section()
        if not section:
            return self
        self.prefix_log = self.prefix_log.with_entry(ContextEntry(kind="skills", title="Novel Skills", body=section))
        return self

    def seed_bible_prefix(self) -> Self:
        """Seed the running prefix with the setting bible so every descendant inherits it.

        The rendered block becomes the first ``setting_bible`` prefix entry; each
        composition walk copies it into every child's prefix log, so chapter,
        story, and scene contexts never hold the bible themselves. Idempotent:
        empty bibles seed nothing and an existing entry is never duplicated.
        """
        if self.series_bible is None or self.series_bible.is_empty():
            return self
        if any(entry.kind == "setting_bible" for entry in self.prefix_log.entries):
            return self
        self.prefix_log = self.prefix_log.with_entry(
            ContextEntry(kind="setting_bible", title="Setting Bible", body=self.series_bible.as_prompt().strip()),
        )
        return self


class RagNovelContext(RagBound, NovelContext[RagChapterContext, NovelPlan]):
    """The RAG run's root channel: every chapter houses RAG-typed stories, and the novel level holds its own references.

    :class:`RagChapterContext` constrains each chapter's children, so reloading a
    persisted RAG run into this class restores the chapters — and through them the
    sealed stories' retrieval state — by pydantic validation alone. Plain
    snapshots fail this stricter validation and load as :class:`NovelContext`.

    The root is where a RAG run retrieves first: the references fetched from the
    novel outline render into the prompts that plan the novel and its chapters —
    and into nothing else, so the scene writers keep seeing only the story-level
    references. The chapters carry the RAG chapter type from the moment they are
    planned, which keeps every stage of a run reloadable as this class.
    """

    rag: RagRetrieval = Field(default_factory=RagRetrieval)
    """Retrieval settings for the novel-level writing style references; defaulted so snapshots written before the novel level retrieved anything still load as this class."""

    @classmethod
    def seal(cls, novel: NovelContext, rag: RagRetrieval) -> "RagNovelContext":
        """Rebind a plain novel root as RAG-bound, carrying the given retrieval settings.

        The rebind copies every field off the plain root's instance state — the
        run-wide constants, the setting bible and the seeded prefix included — so
        only ``rag``, absent from the plain class, is applied on top. Sealing runs
        before the chapters are planned: the children are still empty then, which
        is what lets this class's chapter constraint validate, and the chapter
        planning phase promotes what it creates.

        Sealing an already RAG-bound root returns it unchanged.
        """
        if isinstance(novel, RagNovelContext):
            return novel

        return cls.model_validate({**vars(novel), "rag": rag})
