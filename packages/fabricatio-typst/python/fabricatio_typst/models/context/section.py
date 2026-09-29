"""Pipeline channel model for a section: its plan and the subsection contexts it writes."""

from typing import ClassVar, final

from fabricatio_typst.models.context.base import ParentContextBase
from fabricatio_typst.models.context.log import ContextEntry, EntryKind
from fabricatio_typst.models.context.subsection import SubsectionContext
from fabricatio_typst.models.plan import SectionPlan


class SectionContext[U: SubsectionContext, P: SectionPlan](ParentContextBase[U, P]):
    """A section's composition channel: its plan, subsection contexts and heading block."""

    heading_level: ClassVar[str] = "=="
    """The typst heading marker this section renders under."""

    @property
    def exact_word_count(self) -> int:
        """The word count composed across this section's subsections."""
        return sum(child.exact_word_count for child in self.child_contexts)

    @final
    def render_prefixed_header(self) -> str:
        """Render the section's heading block, seeded into each subsection's prefix.

        Only the heading is emitted: the section elaboration is a synopsis of the text
        that follows, and seeding it would hand each subsection writer the beats of the
        subsections that come after it.
        """
        return f"{self.heading_level} {self.title}"

    @final
    def prefixed_header_entry(self) -> ContextEntry:
        """Wrap the heading block as the header entry seeded into children's prefixes."""
        return ContextEntry(kind=EntryKind.SECTION_HEADER, title=self.title, body=self.render_prefixed_header())

    @final
    def prefixed_entries(self) -> tuple[ContextEntry, ...]:
        """Contribute the heading entry followed by the subsections' entries."""
        entries: list[ContextEntry] = [self.prefixed_header_entry()]
        for child in self.iter_child_contexts():
            entries.extend(child.prefixed_entries())
        return tuple(entries)


__all__ = ["SectionContext"]
