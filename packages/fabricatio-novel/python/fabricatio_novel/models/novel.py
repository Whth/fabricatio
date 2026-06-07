"""This module contains the models for the novel."""

from typing import TYPE_CHECKING, Any, Dict, List, Self

from fabricatio_capabilities.models.generic import PersistentAble, WordCount
from fabricatio_core import TEMPLATE_MANAGER
from fabricatio_core.models.generic import SketchedAble, Titled
from fabricatio_core.rust import word_count

from fabricatio_novel.config import novel_config
from fabricatio_novel.rust import text_to_xhtml_paragraphs

if TYPE_CHECKING:
    from fabricatio_novel.models.plan import ChapterPlan


class Chapter(SketchedAble, PersistentAble, Titled, WordCount):
    """A chapter in a novel."""

    chapter_index: int
    """Zero-based index of this chapter within the novel."""

    content: str
    """Raw chapter text. May contain image references like ![prompt](path).
    Converted to XHTML paragraphs in to_xhtml()."""

    def to_xhtml(self) -> str:
        """Convert the chapter to XHTML format."""
        data: Dict[str, Any] = self.model_dump()
        data["content"] = text_to_xhtml_paragraphs(self.content)
        return TEMPLATE_MANAGER.render_template(novel_config.render_chapter_xhtml_template, data)

    @property
    def exact_word_count(self) -> int:
        """Calculate the exact word count of the chapter."""
        return word_count(self.content)

    @classmethod
    def with_raw_content(cls, raw: str, title: str, expected_word_count: int, chapter_index: int) -> Self:
        """Create a chapter from raw text. Content stored as-is; XHTML conversion deferred to to_xhtml()."""
        return cls(
            content=raw,
            title=title,
            expected_word_count=expected_word_count,
            chapter_index=chapter_index,
        )

    @classmethod
    def from_plan_and_raw_content(cls, chapter_plan: "ChapterPlan", raw: str) -> Self:
        """Create a chapter from a chapter plan and raw generated text."""
        return cls.with_raw_content(
            raw=raw,
            title=chapter_plan.draft.title,
            expected_word_count=chapter_plan.expected_word_count,
            chapter_index=chapter_plan.chapter_index,
        )


class Novel(SketchedAble, PersistentAble, Titled, WordCount):
    """A novel."""

    synopsis: str
    """A summary of the novel's plot."""
    chapters: List[Chapter]
    """List of chapters in the novel."""

    @property
    def exact_word_count(self) -> int:
        """Calculate the exact word count of the novel."""
        return sum(chapter.exact_word_count for chapter in self.chapters)

    @property
    def word_count_compliance_ratio(self) -> float:
        """Calculate the compliance ratio of the novel's word count."""
        return self.exact_word_count / self.expected_word_count
