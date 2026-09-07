"""Pipeline channel model for the novel root: outline, language and chapter contexts."""

from collections.abc import Generator
from typing import Self, final

from fabricatio_core.rust import detect_language

from fabricatio_novel.models.context.base import ParentContextBase
from fabricatio_novel.models.context.chapter import ChapterContext
from fabricatio_novel.models.context.log import ContextEntry
from fabricatio_novel.models.plan import NovelPlan
from fabricatio_novel.models.series_book import SeriesBible


class NovelContext(ParentContextBase[ChapterContext, NovelPlan]):
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

    @classmethod
    def create(cls, outline: str, language: str | None = None) -> Self:
        """Build a novel context from an outline, detecting the language from the outline when none is given."""
        return cls(outline=outline, language=language or detect_language(outline))
