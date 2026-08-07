"""Character state consistency models for novel chapter auditing.

State is a free-form ``str`` (genre-agnostic); a character's transition
sequence is a ``list[str]``. :class:`CharacterState` wraps one character's
change-point sequence with parallel paragraph anchors;
:class:`ChapterStateRecord` aggregates every character of one chapter plus
chapter-level violations.
"""

from typing import List

from fabricatio_core.models.generic import Base, ProposedAble
from pydantic import Field


class CharacterState(Base):
    """One character's state sequence within a chapter (paragraph-anchored)."""

    character: str
    """Character name (matches ``CharacterCard.name``)."""

    states: List[str] = Field(default_factory=list)
    """Ordered change-point sequence of free-form states; consecutive duplicates merged."""

    paragraphs: List[int] = Field(default_factory=list)
    """0-based paragraph indices; SAME length as ``states`` (parallel anchors)."""

    chapter_end_state: str = ""
    """State at the chapter's end; the last ``states`` entry when the character appears."""


class ChapterStateRecord(ProposedAble):
    """Batched extraction result for ONE chapter: every character + violations."""

    characters: List[CharacterState] = Field(default_factory=list)
    """One entry per character demanded by the extraction prompt."""

    violations: List[str] = Field(default_factory=list)
    """Chapter-level, human-readable, paragraph-referenced violations."""
