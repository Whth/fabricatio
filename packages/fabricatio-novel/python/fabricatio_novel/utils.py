"""Utility helpers for the fabricatio novel package."""

from pathlib import Path

from fabricatio_core import logger

__all__ = ["scene_image_name", "strip_overlapping_prefix"]


def scene_image_name(chapter_index: int, scene_index: int) -> Path:
    """Return the file name of a scene's illustration; both indices are 1-based."""
    return Path(f"scene_{chapter_index:02d}_{scene_index:02d}.png")


def _normalized_with_offsets(text: str) -> tuple[str, list[int]]:
    """Collapse whitespace runs to single spaces; return the text and each char's raw end offset."""
    chars: list[str] = []
    offsets: list[int] = []
    pending_space = False
    for i, ch in enumerate(text):
        if ch.isspace():
            if chars:
                pending_space = True
            continue
        if pending_space:
            chars.append(" ")
            offsets.append(i)
            pending_space = False
        chars.append(ch)
        offsets.append(i + 1)
    return "".join(chars), offsets


def strip_overlapping_prefix(
    content: str,
    previous: str,
    *,
    min_chars: int = 40,
    max_ratio: float = 0.6,
) -> str:
    """Remove the previous prose's tail that ``content`` re-emits as its prefix.

    Scene-by-scene generation sometimes makes the model re-emit the end of the
    last scene it saw. Both sides are compared whitespace-normalized (line
    reflows ignored); the longest such match spanning at least ``min_chars``
    normalized characters is stripped from the raw content. When the match
    covers ``max_ratio`` or more of the generated scene the content is kept
    untouched with a warning instead — stripping would leave a stump.
    """
    if not content or not previous or len(content) < min_chars:
        return content
    norm_content, offsets = _normalized_with_offsets(content)
    norm_previous, _ = _normalized_with_offsets(previous)
    window = min(len(norm_previous), len(norm_content))
    tail = norm_previous[len(norm_previous) - window :] if window else ""
    matched = 0
    for length in range(min(window, len(norm_content)), min_chars - 1, -1):
        if tail[-length:] == norm_content[:length]:
            matched = length
            break
    if matched < min_chars:
        return content
    if matched >= len(norm_content) * max_ratio:
        logger.warn(
            f"Generated scene re-emits {matched} of {len(norm_content)} normalized chars of the previous prose; keeping it untouched"
        )
        return content
    stripped = content[offsets[matched - 1] :].lstrip()
    logger.info(f"Stripped a {matched}-char overlapping prefix from the generated scene")
    return stripped
