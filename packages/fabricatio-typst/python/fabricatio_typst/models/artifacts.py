"""Flat container for all intermediate products of the article pipeline."""

from __future__ import annotations

from typing import Optional

from fabricatio_core.utils import ok
from pydantic import BaseModel, Field


class ArticleArtifacts(BaseModel):
    """Stores all intermediate products of the article pipeline.

    Replaces the old ``WithRef`` chain (``Article → ArticleOutline → ArticleProposal → str``)
    with a single flat container that every pipeline stage can read and write.
    """

    briefing: Optional[str] = Field(default=None)
    proposal: Optional[ArticleProposal] = Field(default=None)  # noqa: F821
    outline: Optional[ArticleOutline] = Field(default=None)  # noqa: F821

    model_config = {"arbitrary_types_allowed": True}

    # ------------------------------------------------------------------
    # Accessors — panic with a clear message when the artifact is missing
    # ------------------------------------------------------------------

    def access_briefing(self) -> str:
        """Return the briefing string, raising if it has not been set."""
        return ok(self.briefing, "`briefing` not set. Call `update_briefing` first.")

    def access_proposal(self) -> ArticleProposal:  # noqa: F821
        """Return the proposal, raising if it has not been set."""
        return ok(self.proposal, "`proposal` not set. Call `update_proposal` first.")

    def access_outline(self) -> ArticleOutline:  # noqa: F821
        """Return the outline, raising if it has not been set."""
        return ok(self.outline, "`outline` not set. Call `update_outline` first.")

    # ------------------------------------------------------------------
    # Setters — fluent (return self)
    # ------------------------------------------------------------------

    def update_briefing(self, briefing: str) -> ArticleArtifacts:
        """Set the briefing string."""
        self.briefing = briefing
        return self

    def update_proposal(self, proposal: ArticleProposal) -> ArticleArtifacts:  # noqa: F821
        """Set the proposal."""
        self.proposal = proposal
        return self

    def update_outline(self, outline: ArticleOutline) -> ArticleArtifacts:  # noqa: F821
        """Set the outline."""
        self.outline = outline
        return self

    def update_from(self, other: ArticleArtifacts) -> ArticleArtifacts:
        """Merge non-None fields from *other* into *self*."""
        if other.briefing is not None:
            self.briefing = other.briefing
        if other.proposal is not None:
            self.proposal = other.proposal
        if other.outline is not None:
            self.outline = other.outline
        return self
