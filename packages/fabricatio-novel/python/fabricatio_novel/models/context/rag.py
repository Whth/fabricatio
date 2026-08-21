"""Opt-in writing style retrieval settings carried down the context tree."""

from pydantic import BaseModel


class RagRetrieval(BaseModel):
    """Caller-owned retrieval settings for story-bound writing style references.

    ``None`` on a context means the run uses no RAG; the settings ride the
    context tree so retrieval survives the staged workflow's snapshots.
    """

    query: str = ""
    """Additional query guideline for style retrieval; combined with the story description."""

    limit: int = 15
    """Reference documents kept for the story's scene prompts."""
