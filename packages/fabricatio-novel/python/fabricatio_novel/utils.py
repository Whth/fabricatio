"""Shared formatting utilities for the novel package."""

import re

# Match one or more consecutive blank lines (LF or CRLF, optionally containing
# only spaces/tabs in between). A line of just spaces/tabs is still blank —
# we must not fold that whitespace back into the surrounding paragraphs.
# The trailing `(?:\r?\n)+` collapses runs of 3+ newlines so they don't leave
# a stray prefix on the next paragraph.
_BLANK_LINE_RE = re.compile(r"(?:\r?\n)[ \t]*(?:\r?\n)+")


def formated_title(idx: int, title: str) -> str:
    """Format the title to be used as a filename."""
    return f"Ch-{idx}: {title}"


def last_paragraph(text: str) -> str:
    r"""Return the last non-empty paragraph of ``text``.

    Paragraphs are split on blank lines (LF or CRLF, optionally containing
    only spaces/tabs in between). When the text is empty or contains only
    whitespace, an empty string is returned. Used to give the next-chapter
    writer a focused continuity hook on the prior chapter's closing beat
    without paying the cost of re-feeding the full chapter.
    """
    if not text or not text.strip():
        return ""
    paragraphs = [p.strip() for p in _BLANK_LINE_RE.split(text) if p.strip()]
    return paragraphs[-1] if paragraphs else ""


__all__ = ["formated_title", "last_paragraph"]
