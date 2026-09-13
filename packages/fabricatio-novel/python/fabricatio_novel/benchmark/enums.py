"""The enumerated names the benchmark measures and reports under.

Gate, metric, verdict and direction names are identifiers rather than prose: they
key the per-metric tables, decide whether a comparison regressed, and travel
through the JSON form of a scorecard. Keeping them as str enums means a typo
fails loudly instead of silently naming a different metric — and note that an
enum member hashes by its *name*, so containers keyed by a member must be looked
up with the member, not with a bare string. ``Direction`` is the exception to the
identifier rule: its values are read off the comparison rows.
"""

from enum import StrEnum


class Gate(StrEnum):
    """The hard invariants a run must satisfy; every ``GateFailure`` carries one."""

    GATED_TERMS = "gated_terms"
    """A term the corpus gated appears in the prose."""

    LANGUAGE = "language"
    """The prose script does not match the script of the outline."""

    EXPORT_TEXT = "export_text"
    """An exported chapter disagrees with the scenes."""

    EMPTY_SCENE = "empty_scene"
    """A scene carries no prose."""


class Metric(StrEnum):
    """The continuous metrics two scorecards are compared by."""

    LENGTH_RATIO = "length ratio"
    SCENE_RATIO_MEDIAN = "scene ratio median"
    SCENE_RATIO_MAX = "scene ratio max"
    SEAM_ECHO = "seam echo"
    VERBATIM_SENTENCES = "verbatim sentences"
    MAX_SCENE_OVERLAP = "max scene overlap"

    SENTENCE_CHARS = "sentence chars"
    """Mean sentence length in characters."""

    SENTENCE_VARIATION = "sentence variation"
    """How much sentence lengths vary, as the coefficient of variation."""

    LONG_SENTENCE_RATIO = "long sentence ratio"
    """Share of sentences at or above the long-sentence threshold."""

    VOCAB_RECYCLED_PER_1K = "vocab recycled per 1k"
    """Repeated n-grams per 1000, averaged over fixed-size windows."""

    GATED_TERMS = "gated terms"
    WATCH_RATE_PER_1K = "watch rate per 1k"
    DURATION_SECONDS = "duration seconds"


class Direction(StrEnum):
    """Which way a metric has to move to count as an improvement."""

    LOWER = "lower"
    """A decrease is the improvement."""

    HIGHER = "higher"
    """An increase is the improvement."""

    NEUTRAL = "neutral"
    """Neither direction is better: an out-of-band move is reported as drift, not as a verdict."""


class Verdict(StrEnum):
    """The direction of one metric's change, or of a whole comparison."""

    IMPROVED = "improved"
    REGRESSED = "regressed"
    DRIFTED = "drifted"
    """A directionless metric moved outside its noise band."""

    NOISE = "noise"
    """The change stays inside the metric's band."""

    UNCHANGED = "unchanged"
    """Comparison-only: no gate moved and the metrics cancelled out."""
