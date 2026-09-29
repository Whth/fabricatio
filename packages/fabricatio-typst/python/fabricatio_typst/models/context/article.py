"""Pipeline channel model for the article root: its plan, the chapter contexts and the run artifacts."""

from typing import Self, final

from pydantic import Field

from fabricatio_typst.models.artifacts import ArticleArtifacts
from fabricatio_typst.models.context.base import ParentContextBase
from fabricatio_typst.models.context.chapter import ChapterContext
from fabricatio_typst.models.context.log import ContextEntry, EntryKind
from fabricatio_typst.models.plan import ArticlePlan


class ArticleContext[C: ChapterContext, P: ArticlePlan](ParentContextBase[C, P]):
    """The article root channel: its plan, the chapter contexts it writes and the run's artifacts.

    The run-wide constants every level renders (language, briefing, proposal, skills)
    start here and are copied down each creation chain.
    """

    artifacts: ArticleArtifacts = Field(default_factory=ArticleArtifacts)
    """The run's intermediate products — briefing, proposal and the assembled outline — kept together on
    the root so a dump or a resume finds them in one place."""

    @property
    def exact_word_count(self) -> int:
        """The word count composed across the whole article."""
        return sum(child.exact_word_count for child in self.child_contexts)

    @final
    def seed_outline_prefix(self, outline: str) -> Self:
        """Seed the rendered article outline into the running prefix, once.

        Every descendant of the root inherits the seed through its prefix, so a
        subsection writer sees the paper's whole structure above the running text; the
        entry is appended at most once, so repeated walks render the same bytes and a
        resumed tree that already carries it stays untouched.
        """
        if any(entry.kind.is_article_outline() for entry in self.prefix_log.entries):
            return self
        return self.set_prefix_log(
            self.prefix_log.with_entry(ContextEntry(kind=EntryKind.ARTICLE_OUTLINE, title=self.title, body=outline)),
        )

    @final
    def prefixed_entries(self) -> tuple[ContextEntry, ...]:
        """Forward the chapters' entries; the article's own heading and abstract are not injected."""
        entries: list[ContextEntry] = []
        for child in self.iter_child_contexts():
            entries.extend(child.prefixed_entries())
        return tuple(entries)


__all__ = ["ArticleContext"]
