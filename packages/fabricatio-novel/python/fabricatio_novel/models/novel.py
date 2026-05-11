"""This module contains the models for the novel."""

from functools import cached_property
from typing import TYPE_CHECKING, Any, Dict, Generator, List, Self, Tuple

from fabricatio_capabilities.models.generic import PersistentAble, WordCount
from fabricatio_core import TEMPLATE_MANAGER
from fabricatio_core.models.generic import Language, SketchedAble, Titled
from fabricatio_core.rust import word_count

from fabricatio_novel.config import novel_config
from fabricatio_novel.rust import text_to_xhtml_paragraphs
from fabricatio_novel.utils import formated_title

if TYPE_CHECKING:
    from fabricatio_novel.models.plan import ChapterPlan


class ChapterDraft(Titled):
    """Chapter Draft for early stage novel design."""

    title: str
    """Chunk part of title of the Chapter. AKA, title with chap index omit"""

    synopsis: str
    """
    Super detailed summaries for each chapter.
    Cover: what happens, how characters change, key scenes/dialogue, setting shifts, emotional tone, and hints or themes.
    Goal: Lock in every important detail so nothing gets lost later — like a mini-script for each chapter.
    """
    weight: float
    """The weight of the chapter. higher values means more words count allocation."""


class NovelDraft(SketchedAble, Titled, Language, PersistentAble, WordCount):
    """A draft representing a novel, including its title, genre, characters, chapters, and synopsis."""

    title: str
    """The title of the novel."""
    genre: List[str]
    """The genres of the novel. Comprehensive coverage is preferred than few ones."""

    synopsis: str
    """A summary of the novel's plot."""

    character_descriptions: List[str]
    """
    Super detailed descriptions for each main character.
    Include: looks, personality, backstory, goals, relationships, inner struggles, and their role in the story.
    Goal: Make every character feel real, consistent, and fully fleshed out — no vague or shallow summaries.
    """

    chapters: List[ChapterDraft]

    expected_word_count: int
    """The expected word count of the novel."""

    @property
    def total_chapters(self) -> int:
        return len(self.chapters)

    @property
    def all_chapters_titles(self) -> List[str]:
        return [formated_title(i, chapter.title) for i, chapter in enumerate(self.chapters)]

    def iter_chap(self) -> Generator[Tuple[int, int, ChapterDraft], None, None]:
        """Iterate through all chapters with metadata."""
        for i, (
            expected_word_count,
            chapter,
        ) in enumerate(zip(self.chapter_expected_word_counts, self.chapters, strict=True)):
            yield i, expected_word_count, chapter

    def iter_ft_chap(self) -> Generator[Tuple[str, int, ChapterDraft], None, None]:
        for idx, wc, chap in self.iter_chap():
            yield formated_title(idx, chap.title), wc, chap

    @cached_property
    def chapter_expected_word_counts(self) -> List[int]:
        """Calculate the expected word count for each chapter."""
        weights = [c.weight for c in self.chapters]
        weights_sum = sum(weights)

        return [int(self.expected_word_count * wc / weights_sum) for wc in weights]


class Chapter(SketchedAble, PersistentAble, Titled, WordCount):
    """A chapter in a novel."""

    chapter_index: int

    content: str
    """The content of the chapter."""

    def to_xhtml(self) -> str:
        """Convert the chapter to XHTML format."""
        data: Dict[str, Any] = self.model_dump()
        return TEMPLATE_MANAGER.render_template(novel_config.render_chapter_xhtml_template, data)

    @property
    def exact_word_count(self) -> int:
        """Calculate the exact word count of the chapter."""
        return word_count(self.content)

    @classmethod
    def with_raw_content(cls, raw: str, title: str, expected_word_count: int, chapter_index: int) -> Self:
        cleaned_content = text_to_xhtml_paragraphs(raw)
        return cls(
            content=cleaned_content,
            title=title,
            expected_word_count=expected_word_count,
            chapter_index=chapter_index,
        )

    @classmethod
    def from_plan_and_raw_content(cls, chapter_plan: "ChapterPlan", raw: str) -> Self:
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
