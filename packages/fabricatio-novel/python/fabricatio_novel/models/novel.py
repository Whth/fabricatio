"""This module contains the models for the novel."""

from typing import Any, List

from fabricatio_capabilities.models.generic import PersistentAble, WordCount
from fabricatio_core import TEMPLATE_MANAGER
from fabricatio_core.models.generic import Language, SketchedAble, Titled
from fabricatio_core.rust import logger, word_count

from fabricatio_novel.config import novel_config


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
    Every string in this list MUST be at least 180 words.
    Super detailed descriptions for each main character.
    Include: looks, personality, backstory, goals, relationships, inner struggles, and their role in the story.
    Goal: Make every character feel real, consistent, and fully fleshed out — no vague or shallow summaries.
    """

    chapter_synopses: List[str]
    """
    Every string in this list MUST be at least 270 words.
    Super detailed summaries for each chapter.
    Cover: what happens, how characters change, key scenes/dialogue, setting shifts, emotional tone, and hints or themes.
    Goal: Lock in every important detail so nothing gets lost later — like a mini-script for each chapter.
    """
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


class Chapter(SketchedAble, PersistentAble, Titled, WordCount):
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
