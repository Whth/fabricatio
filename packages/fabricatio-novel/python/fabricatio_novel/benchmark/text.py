"""Text primitives shared by every benchmark metric.

Chinese and English runs go through the same code path: Chinese is measured in
character n-grams (whitespace carries no meaning there) and English in word
n-grams, so a scorecard means the same thing for a Chinese and an English run.
Sentences come from the core's Unicode segmentation and word counts from the
core's word counter, so no metric can disagree with the pipeline about how long
a piece of prose is. Everything here is pure, so the metrics are reproducible
from the artifacts alone.
"""

import re

from fabricatio_core.rust import split_sentence_bounds

CJK_RUN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+")
"""A run of CJK characters; the unit that CJK terms are cut from."""

WORD = re.compile(r"[0-9A-Za-z_]+")
"""A Latin word; the unit that non-CJK terms are cut from."""

_TERM_SIZES = (3, 4)
"""CJK term lengths: CJK has no word boundaries, so terms are cut at the sizes that carry most short phrases."""

_WORD_MIN_CHARS = 4
"""Latin terms shorter than this are function words in practice (the, and, with) and carry no beat."""


def normalize(text: str) -> str:
    """Collapse every whitespace run into a single space."""
    return " ".join(text.split())


def compact(text: str) -> str:
    """Return the text without any whitespace, the form used for character n-grams."""
    return "".join(text.split())


def char_ngrams(text: str, size: int) -> set[str]:
    """Return the distinct character n-grams of the whitespace-stripped text."""
    body = compact(text)
    return {body[start : start + size] for start in range(max(len(body) - size + 1, 0))}


def char_gram_stream(text: str, size: int) -> list[str]:
    """Return every character n-gram of the whitespace-stripped text, repeats included.

    :func:`char_ngrams` answers "which n-grams occur" for the overlap metrics;
    the repetition metrics need "how often", and measuring in characters keeps
    them script-agnostic — no word boundaries, no stopword list, no language
    branch, so a Chinese and an English run are measured by the same rule.
    """
    body = compact(text)
    return [body[start : start + size] for start in range(max(len(body) - size + 1, 0))]


def ngram_overlap(left: str, right: str, size: int) -> float:
    """Return the fraction of ``left``'s character n-grams that also occur in ``right``."""
    left_grams = char_ngrams(left, size)
    if not left_grams:
        return 0.0
    return len(left_grams & char_ngrams(right, size)) / len(left_grams)


def significant_terms(text: str) -> set[str]:
    """Return the distinctive terms of the text: every CJK 3..4-char n-gram and Latin words of 4+ chars lowercased.

    Ordinary prose vocabulary is not filtered out here on purpose: the term sets
    are only ever compared against other term sets of the same run, where the
    plan text supplies the licence for every word it uses.
    """
    terms: set[str] = set()
    for match in CJK_RUN.finditer(text):
        run = match.group()
        for size in _TERM_SIZES:
            terms.update(run[start : start + size] for start in range(max(len(run) - size + 1, 0)))
    terms.update(word.lower() for word in WORD.findall(text) if len(word) >= _WORD_MIN_CHARS)
    return terms


def sentences(text: str) -> list[str]:
    """Split the text into sentences with the core's Unicode sentence segmentation.

    UAX#29 ends a sentence by the same rules in every script, which is what makes
    a length measured on Chinese and on English prose comparable: a CJK ender
    always closes a sentence, an ASCII period closes one outside a decimal or an
    abbreviation, and an ellipsis closes none. The ender stays attached to the
    sentence it closes and the whitespace around it is normalized away, so a
    sentence reads as it did in the prose.
    """
    return [normalized for piece in split_sentence_bounds(text) if (normalized := normalize(piece))]


def cjk_ratio(text: str) -> float:
    """Return the fraction of non-whitespace characters that are CJK; 0.0 for an empty text."""
    body = compact(text)
    if not body:
        return 0.0
    return sum(len(match.group()) for match in CJK_RUN.finditer(body)) / len(body)
