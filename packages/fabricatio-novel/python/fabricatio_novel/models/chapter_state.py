"""Character state consistency models for novel chapter auditing.

State is a free-form ``str`` (genre-agnostic); a character's transition
sequence is a ``list[str]``. :class:`CharacterState` wraps one character's
change-point sequence with parallel paragraph anchors;
:class:`ChapterStateRecord` aggregates every character of one chapter plus
chapter-level violations. :class:`CharacterStateEntry`/:class:`StateBoard`
are serialization payloads for the state-board prompt injection.
"""

from typing import List, Optional

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


class CharacterStateEntry(Base):
    """One character's latest known state, as rendered on the state board.

    ``has_chapter`` distinguishes "recorded end state" (``state``/``chapter``
    populated) from "no state recorded yet" (first-chapter baseline).
    """

    name: str
    """Character name (matches ``CharacterCard.name``)."""

    state: Optional[str] = None
    """The character's latest chapter-end state; ``None`` when none recorded."""

    chapter: Optional[int] = None
    """Chapter index the latest end state was recorded at; ``None`` when none recorded."""

    has_chapter: bool = False
    """Whether an end state has been recorded (``state``/``chapter`` are populated)."""


class StateBoard(Base):
    """Serialized payload for the Character State Board template.

    Built on the caller-owned channel by ``StateChapterContext.state_board_context``
    and dumped with ``model_dump()`` at the template engine boundary.
    """

    states: List[CharacterStateEntry] = Field(default_factory=list)
    """One entry per character, sorted by name."""

    warnings: List[str] = Field(default_factory=list)
    """Deduplicated, order-preserving human-readable violations."""


class ChapterStateRecord(ProposedAble):
    """Batched extraction result for ONE chapter: every character + violations."""

    characters: List[CharacterState] = Field(default_factory=list)
    """One entry per character demanded by the extraction prompt."""

    violations: List[str] = Field(default_factory=list)
    """Chapter-level, human-readable, paragraph-referenced violations."""
