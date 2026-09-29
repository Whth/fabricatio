"""Pipeline channel model for a chapter: its plan and the section contexts it writes."""

from typing import ClassVar, final

from fabricatio_typst.models.context.base import ParentContextBase
from fabricatio_typst.models.context.log import ContextEntry, EntryKind
from fabricatio_typst.models.context.section import SectionContext
from fabricatio_typst.models.plan import ChapterPlan


class ChapterContext[S: SectionContext, P: ChapterPlan](ParentContextBase[S, P]):
    """A chapter's composition channel: its plan, section contexts and heading block."""

    heading_level: ClassVar[str] = "="
    """The typst heading marker this chapter renders under."""

    @property
    def exact_word_count(self) -> int:
        """The word count composed across this chapter's sections."""
        return sum(child.exact_word_count for child in self.child_contexts)

    @final
    def render_prefixed_header(self) -> str:
        """Render the chapter's heading block, seeded into each section's prefix.

        Only the heading is emitted: the chapter elaboration is a whole-chapter
        synopsis, and seeding it would hand every descendant writer the beats of the
        sections that come after it.
        """
        return f"{self.heading_level} {self.title}"

    @final
    def prefixed_header_entry(self) -> ContextEntry:
        """Wrap the heading block as the header entry seeded into children's prefixes."""
        return ContextEntry(kind=EntryKind.CHAPTER_HEADER, title=self.title, body=self.render_prefixed_header())

    @final
    def prefixed_entries(self) -> tuple[ContextEntry, ...]:
        """Contribute the heading entry followed by the sections' entries."""
        entries: list[ContextEntry] = [self.prefixed_header_entry()]
        for child in self.iter_child_contexts():
            entries.extend(child.prefixed_entries())
        return tuple(entries)


__all__ = ["ChapterContext"]
