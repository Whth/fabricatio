"""The sentence form every prose metric is read through.

The counting itself lives in Rust (``fabricatio_novel.rust``): the character
n-grams, the term sets, the script ratio, the scene-pair overlaps and the probe
term counts are all measured there, so a Chinese and an English run go through
one rule at the speed a scoring pass needs.

What stays here is the sentence: UAX#29 segmentation from the core with the
whitespace around each sentence normalized away, so no metric can disagree with
the pipeline about how long a piece of prose is. Everything here is pure, so the
metrics are reproducible from the artifacts alone.
"""

from fabricatio_core.rust import split_sentence_bounds


def normalize(text: str) -> str:
    """Collapse every whitespace run into a single space."""
    return " ".join(text.split())


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
