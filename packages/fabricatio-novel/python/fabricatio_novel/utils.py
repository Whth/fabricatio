"""Utility helpers for the fabricatio novel package."""

__all__ = ["scene_image_name"]


def scene_image_name(chapter_index: int, scene_index: int) -> str:
    """Return the EPUB resource name of a scene's illustration; both indices are 1-based."""
    return f"images/scene_{chapter_index:02d}_{scene_index:02d}.png"
