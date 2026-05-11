"""Shared formatting utilities for the novel package."""


def formated_title(idx: int, title: str) -> str:
    """Format the title to be used as a filename."""
    return f"Ch-{idx}: {title}"
