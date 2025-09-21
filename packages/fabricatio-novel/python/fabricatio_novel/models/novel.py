"""This module contains the models for the novel."""

from typing import List

from fabricatio_core import TEMPLATE_MANAGER
from fabricatio_core.models.generic import Language, SketchedAble, Titled
from fabricatio_typst.models.generic import WordCount

from fabricatio_novel.config import novel_config


class NovelDraft(SketchedAble, Titled, Language, WordCount):
    """A draft representing a novel, including its title, genre, characters, chapters, and synopsis."""

    title: str
    """The title of the novel."""
    genre: List[str]
    """The genres of the novel."""

    synopsis: str
    """A brief summary of the novel's plot."""

    character_desc: List[str]
    """List of descriptions for each character in the novel."""

    chapter_synopses: List[str]
    """List of synopses for each chapter in the novel."""

    expected_word_count: int
    """The expected word count of the novel."""


class Chapter(SketchedAble, Titled, WordCount):
    """A chapter in a novel."""

    content: str
    """The content of the chapter."""

    def to_xhtml(self) -> str:
        """Convert the chapter to XHTML format."""
        return TEMPLATE_MANAGER.render_template(novel_config.render_chapter_xhtml_template, self.model_dump())


class Novel(SketchedAble, Titled):
    """A novel."""

    chapters: List[Chapter]
    """List of chapters in the novel."""
