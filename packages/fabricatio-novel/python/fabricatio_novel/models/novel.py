"""This module contains the models for the novel."""

from typing import List

from fabricatio_core.models.generic import SketchedAble, Titled


class NovelDraft(SketchedAble, Titled):
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


class Chapter(SketchedAble, Titled):
    """A chapter in a novel."""

    content: str
    """The content of the chapter."""


class Novel(SketchedAble, Titled):
    chapters: List[Chapter]
    """List of chapters in the novel."""
