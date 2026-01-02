"""Note module for representing memory notes.

This module defines the Note class which represents a memory note with content, importance,
and tags. It is designed to work within the fabricatio_memory package and extends the
SketchedAble base class.
"""

from typing import List

from fabricatio_core.models.generic import SketchedAble
from pydantic import Field

from fabricatio_memory.rust import MIN_IMPORTANCE_SCORE, MAX_IMPORTANCE_SCORE


class Note(SketchedAble):
    """A memory note."""

    content: str
    """Textual content of the memory."""

    importance: int = Field(ge=MIN_IMPORTANCE_SCORE, le=MAX_IMPORTANCE_SCORE)
    """Numerical value representing the importance of the memory. The higher, the more important."""

    tags: List[str]
    """List of string tags associated with the memory for categorization and searching."""
