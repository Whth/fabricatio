"""This module contains the models for the novel."""

from typing import Any, List

from fabricatio_core import TEMPLATE_MANAGER
from fabricatio_core.models.generic import Language, SketchedAble, Titled
from fabricatio_core.rust import logger, word_count
from fabricatio_typst.models.generic import WordCount

from fabricatio_novel.config import novel_config


class NovelDraft(SketchedAble, Titled, Language, WordCount):
    """A draft representing a novel, including its title, genre, characters, chapters, and synopsis."""

    title: str
    """The title of the novel."""
    genre: List[str]
    """The genres of the novel. Comprehensive coverage is preferred than few ones."""

    synopsis: str
    """A summary of the novel's plot."""

    character_desc: List[str]
    """List of extremely detailed descriptions for each character in the novel. which should contains everything about the character in the reference material."""

    chapter_synopses: List[str]
    """List of extremely detailed synopses for each chapter in the novel."""

    expected_word_count: int
    """The expected word count of the novel."""

    chapter_expected_word_counts: List[int]
    """List of expected word counts for each chapter in the novel. should be the same length as chapter_synopses."""

    def model_post_init(self, context: Any, /) -> None:
        """Make sure that the chapter expected word counts are aligned with the chapter synopses."""
        if len(self.chapter_synopses) != len(self.chapter_expected_word_counts):
            if self.chapter_expected_word_counts:
                logger.warn(
                    "Chapter expected word counts are not aligned with chapter synopses, using the last valid one to fill the rest."
                )
                # If word counts are not aligned, copy the last valid chapter's word count
                last_valid_wc = self.chapter_expected_word_counts[-1]
                self.chapter_expected_word_counts.extend(
                    [last_valid_wc] * (len(self.chapter_synopses) - len(self.chapter_expected_word_counts))
                )
            else:
                logger.warn("No chapter expected word counts provided, using the expected word count to fill the list.")
                # If the word count list is totally empty, distribute the expected word count evenly
                avg_wc = self.expected_word_count // len(self.chapter_synopses)
                self.chapter_expected_word_counts = [avg_wc] * len(self.chapter_synopses)


class Chapter(SketchedAble, Titled, WordCount):
    """A chapter in a novel."""

    content: str
    """The content of the chapter."""

    def to_xhtml(self) -> str:
        """Convert the chapter to XHTML format."""
        return TEMPLATE_MANAGER.render_template(novel_config.render_chapter_xhtml_template, self.model_dump())

    @property
    def exact_word_count(self) -> int:
        """Calculate the exact word count of the chapter."""
        return word_count(self.content)


class Novel(SketchedAble, Titled, WordCount):
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
