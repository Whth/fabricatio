"""Pipeline channel model for a subsection: its plan and the composed prose it owns."""

from typing import Self, final

from fabricatio_core.rust import word_count

from fabricatio_typst.models.context.base import ContextBase
from fabricatio_typst.models.context.log import ContextEntry, EntryKind
from fabricatio_typst.models.plan import SubsectionPlan


class SubsectionContext(ContextBase[SubsectionPlan]):
    """A subsection's composition channel: its plan and the composed prose it owns."""

    content: str = ""
    """The composed prose of this subsection, paragraphs separated by blank lines; the only context level
    that owns composed content."""

    def set_content(self, content: str) -> Self:
        """Set the subsection's composed prose and return self."""
        self.content = content
        return self

    @property
    def exact_word_count(self) -> int:
        """The word count of the prose composed so far."""
        return word_count(self.content)

    def is_section_opening(self) -> bool:
        """Whether this subsection opens its section, no prose of that section existing above it.

        Everything above the subsection is the earlier chapters and sections with their
        headings, with the seeded article outline carrying no prose of its own. So the
        section has already started exactly when the newest composed block above the
        subsection is prose; when the newest one is the section's heading, the prompt has
        to say that this subsection opens the section — its instruction to continue the
        text above would otherwise point at a heading.
        """
        written = [
            entry.kind
            for entry in self.prefix_log.entries
            if entry.kind.is_section_header() or entry.kind.is_subsection_content()
        ]
        return not written or written[-1].is_section_header()

    @final
    def prefixed_entries(self) -> tuple[ContextEntry, ...]:
        """Contribute the composed prose; subsection headings and elaborations are not injected."""
        if not self.content:
            return ()
        return (ContextEntry(kind=EntryKind.SUBSECTION_CONTENT, title=self.title, body=self.content),)


__all__ = ["SubsectionContext"]
