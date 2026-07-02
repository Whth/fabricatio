"""Corpus cleanup capability for pre-embedding hygiene.

Provides deterministic, composable cleaning steps that operate on a corpus
(strings or document-like objects) before it is chunked, embedded, and stored.

Pipeline order (each step is opt-in via its own guard in the config):

    raw -> normalize -> strip_markup -> mask_pii -> lang_filter
        -> split -> dedup -> length_filter -> cleaned

LLM-based enrichment (summaries, hypothetical questions, etc.) is intentionally
NOT part of this class — it belongs in a separate, opt-in capability.
"""

import asyncio
from typing import List, overload

from fabricatio_diff.capabilities.hashline_edit import HashlineEdit


class CleanText(HashlineEdit):
    """Clean text using LLM-guided hashline edits.

    Each call to :meth:`clean` delegates to
    :meth:`HashlineEdit.hashline_diff`, which runs a self-correcting LLM
    loop: the LLM emits hashline-anchored edits, they are applied via Rust
    primitives, and the result is judged against the guideline. If the judge
    rejects it, the loop retries with the error context.
    """

    @overload
    async def clean(self, clean_guideline: str, text: str) -> str: ...
    @overload
    async def clean(self, clean_guideline: str, text: List[str]) -> List[str]: ...
    @overload
    async def clean(
        self,
        clean_guideline: str,
        text: str | List[str],
    ) -> str | List[str]: ...
    async def clean(
        self,
        clean_guideline: str,
        text: str | List[str],
    ) -> str | List[str]:
        """Clean text(s) until they satisfy the given guideline.

        Args:
            clean_guideline: Natural-language description of the target clean
                state (e.g. ``"Remove all HTML tags"``).
            text: Single string or list of strings to clean.

        Returns:
            For a single str: the cleaned string.
            For a list of str: a list of cleaned strings, preserving order.

        Raises:
            HashlineEditExhaustedError: If the LLM cannot satisfy the
                guideline within the configured iteration limit.
        """
        was_str = isinstance(text, str)
        texts = [text] if was_str else text
        # hashline_diff is per-text with no shared mutable state, so the
        # per-input loop is embarrassingly parallel.
        results = await asyncio.gather(*(self.hashline_diff(t, clean_guideline) for t in texts))
        contents = [r.content for r in results]

        return contents[0] if was_str else contents
