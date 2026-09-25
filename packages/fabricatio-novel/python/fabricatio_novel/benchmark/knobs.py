"""The knobs every benchmark measure reads a run by.

The sizes the Rust measures read a run at are calibrated on the Rust side
(``fabricatio_novel.rust.Knobs``); the package configuration may override any of
them under ``[ext.novel.benchmark]``, so a scorecard can be taken at other sizes
than the calibrated ones without a code change. The two thresholds only the
Python side applies — a duplicate sentence's shortest length and a long
sentence's length — are calibrated next to the code that applies them.
"""

from fabricatio_novel.config import novel_config
from fabricatio_novel.rust import Knobs

DUPLICATE_MIN_CHARS = 10
"""Shortest whitespace-normalized sentence counted as a verbatim duplicate; shorter fragments match across ordinary narration."""

LONG_SENTENCE_CHARS = 80
"""A sentence from here on counts as long: about fifteen English words, a run-on in Chinese."""


def benchmark_knobs() -> Knobs:
    """The knobs in force: ``[ext.novel.benchmark]``, over the measures' own calibrated defaults."""
    configured = novel_config.benchmark
    return Knobs(
        pair_size=configured.pair_size,
        seam_size=configured.seam_size,
        seam_window=configured.seam_window,
        echo_warn=configured.echo_warn,
        vocab_size=configured.vocab_size,
        vocab_window=configured.vocab_window,
        vocab_tops=configured.vocab_tops,
    )


def duplicate_min_chars() -> int:
    """The shortest sentence counted as a verbatim duplicate."""
    configured = novel_config.benchmark.duplicate_min_chars
    return DUPLICATE_MIN_CHARS if configured is None else configured


def long_sentence_chars() -> int:
    """The length from which a sentence counts as long."""
    configured = novel_config.benchmark.long_sentence_chars
    return LONG_SENTENCE_CHARS if configured is None else configured
