"""Module for the Sequential Thinking model.

Sequential Thinking process. It includes various attributes to describe the
thought content, progression control, revision information, and branching
details.
"""

from typing import Optional

from fabricatio_core.models.generic import SketchedAble


class Thought(SketchedAble):
    """Represents a single step in Sequential Thinking."""

    thought: str
    """The content of the current thought step."""
    end: bool
    """Whether to continue the thinking process."""
    serial: int
    """The number of the current step (starting from 1)."""
    estimated: int
    """The estimated total number of thought steps."""
    revision: bool = False
    """Whether this is a revision of a previous step."""
    revises_thought: Optional[int] = None
    """The step number being revised."""
    checkout: Optional[int] = None
    """The step number from which a branch is created."""
    branch: Optional[str] = None
    """Unique identifier for the branch."""
