"""Note module for representing memory notes.

This module defines the Note class which represents a memory note with content, importance,
and tags. It is designed to work within the fabricatio_memory package and extends the
SketchedAble base class.
"""

from typing import List

from fabricatio_core.models.generic import SketchedAble
from pydantic import Field


class Note(SketchedAble):
    """A memory note."""

    content: str
    """Textual content of the memory."""

    importance: float = Field(ge=0, le=1)
    """Numerical value representing the importance of the memory (0.0 to 1.0)."""

    tags: List[str]
    """List of string tags associated with the memory for categorization and searching."""
