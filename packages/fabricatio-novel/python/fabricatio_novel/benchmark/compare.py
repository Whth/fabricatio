"""Compare a candidate run against a baseline: hard gates, continuous deltas, paired scenes.

Sample noise is the central problem of measuring a stochastic pipeline: runs of a
reference corpus differ by more than 20% on length with everything else held
equal, so a single-pair difference is not evidence on its own. Two mechanisms
keep the verdict honest — hard gates (gated probe terms, export integrity,
script fidelity) are binary and cannot be sampling noise, and runs sharing a
``plan_fingerprint`` are compared per scene, with an exact sign test over the
scenes that changed.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from fabricatio_novel.benchmark.enums import Direction, Metric, Verdict
from fabricatio_novel.benchmark.models import Comparison, MetricDelta, RunScorecard
from fabricatio_novel.benchmark.probes import TermProbes
from fabricatio_novel.benchmark.scorecard import score_run

RELATIVE_BAND = 0.2
"""A continuous metric within ±20% of its baseline is reported as noise."""

BASELINE_SCAN = 12
"""How many earlier sibling runs to score while looking for a comparable baseline, newest first."""


@dataclass(frozen=True, slots=True)
class MetricSpec:
    """One continuous metric: how to read it off a scorecard, and which direction is better."""

    name: Metric
    read: Callable[[RunScorecard], float]
    direction: Direction

    def delta(self, baseline: RunScorecard, candidate: RunScorecard) -> MetricDelta:
        """Measure this metric's change between two scorecards.

        A change inside the relative band counts as noise, and a directionless
        metric has no better side: an out-of-band move of one is reported as drift
        instead of as an improvement or a regression.
        """
        before = self.read(baseline)
        after = self.read(candidate)
        change: float | None = None
        if before == 0.0:
            verdict = Verdict.NOISE if after == 0.0 else _OFF_ZERO[self.direction]
        else:
            change = (after - before) / before
            if abs(change) <= RELATIVE_BAND:
                verdict = Verdict.NOISE
            elif self.direction == Direction.NEUTRAL:
                verdict = Verdict.DRIFTED
            else:
                worse = after > before if self.direction == Direction.LOWER else after < before
                verdict = Verdict.REGRESSED if worse else Verdict.IMPROVED
        return MetricDelta(metric=self.name, baseline=before, candidate=after, relative_change=change, verdict=verdict)


METRICS: tuple[MetricSpec, ...] = (
    MetricSpec(Metric.LENGTH_RATIO, lambda card: card.ratio, Direction.LOWER),
    MetricSpec(Metric.SCENE_RATIO_MEDIAN, lambda card: card.scene_ratio_median, Direction.LOWER),
    MetricSpec(Metric.SCENE_RATIO_MAX, lambda card: card.scene_ratio_max, Direction.LOWER),
    MetricSpec(Metric.SEAM_ECHO, lambda card: card.repetition.max_boundary_echo, Direction.LOWER),
    MetricSpec(
        Metric.VERBATIM_SENTENCES, lambda card: float(len(card.repetition.duplicate_sentences)), Direction.LOWER
    ),
    MetricSpec(Metric.MAX_SCENE_OVERLAP, lambda card: card.repetition.max_pair_overlap, Direction.LOWER),
    MetricSpec(Metric.SENTENCE_CHARS, lambda card: card.prose.sentences.mean_chars, Direction.NEUTRAL),
    MetricSpec(Metric.SENTENCE_VARIATION, lambda card: card.prose.sentences.variation, Direction.NEUTRAL),
    MetricSpec(Metric.LONG_SENTENCE_RATIO, lambda card: card.prose.sentences.long_ratio, Direction.LOWER),
    MetricSpec(Metric.VOCAB_RECYCLED_PER_1K, lambda card: card.prose.vocabulary.recycled_per_1k, Direction.LOWER),
    MetricSpec(Metric.GATED_TERMS, lambda card: float(card.probes.gated_total), Direction.LOWER),
    MetricSpec(Metric.WATCH_RATE_PER_1K, lambda card: card.probes.watch_per_1k, Direction.LOWER),
    MetricSpec(Metric.DURATION_SECONDS, lambda card: card.duration_s, Direction.LOWER),
)


_OFF_ZERO: dict[Direction, Verdict] = {
    Direction.LOWER: Verdict.REGRESSED,
    Direction.HIGHER: Verdict.IMPROVED,
    Direction.NEUTRAL: Verdict.DRIFTED,
}
"""The verdict a metric gets when it moves off a zero baseline.

Zero is the state the reference corpus verified as clean, so a metric that moves
off zero is never noise, however small the absolute number is.
"""


def sign_test_p(shorter: int, longer: int) -> float | None:
    """Return the exact two-sided binomial p-value for the paired sign test, or ``None`` with no changed scenes."""
    total = shorter + longer
    if total == 0:
        return None
    tail = sum(math.comb(total, index) for index in range(min(shorter, longer) + 1)) / 2**total
    return min(1.0, 2 * tail)


def compare(baseline: RunScorecard, candidate: RunScorecard) -> Comparison:
    """Measure a candidate scorecard against a baseline scorecard.

    Gate movement decides the verdict first, then the balance of improved and
    regressed metrics; a directionless metric that drifted is reported per row
    and never decides the comparison on its own.
    """
    deltas = [spec.delta(baseline, candidate) for spec in METRICS]
    paired = baseline.plan_fingerprint == candidate.plan_fingerprint and baseline.scene_count == candidate.scene_count
    shorter = longer = 0
    if paired:
        for old, new in zip(baseline.scenes, candidate.scenes, strict=True):
            shorter += new.ratio < old.ratio
            longer += new.ratio > old.ratio

    baseline_gates = {failure.gate for failure in baseline.gates_failed}
    candidate_gates = {failure.gate for failure in candidate.gates_failed}
    new_failures = [failure for failure in candidate.gates_failed if failure.gate not in baseline_gates]
    fixed_failures = [failure for failure in baseline.gates_failed if failure.gate not in candidate_gates]

    regressed = sum(1 for delta in deltas if delta.verdict == Verdict.REGRESSED)
    improved = sum(1 for delta in deltas if delta.verdict == Verdict.IMPROVED)
    if new_failures:
        verdict = Verdict.REGRESSED
    elif fixed_failures and not regressed:
        verdict = Verdict.IMPROVED
    elif regressed > improved:
        verdict = Verdict.REGRESSED
    elif improved > regressed:
        verdict = Verdict.IMPROVED
    else:
        verdict = Verdict.UNCHANGED

    return Comparison(
        baseline_run=baseline.run,
        candidate_run=candidate.run,
        paired=paired,
        scene_pairs=len(candidate.scenes) if paired else 0,
        scenes_shorter=shorter,
        scenes_longer=longer,
        sign_test_p=sign_test_p(shorter, longer) if paired else None,
        deltas=deltas,
        new_gate_failures=new_failures,
        fixed_gate_failures=fixed_failures,
        verdict=verdict,
    )


def find_baseline(
    candidate: RunScorecard, *, scan: int = BASELINE_SCAN, probes: TermProbes | None = None
) -> RunScorecard | None:
    """Return the newest earlier run in the same directory, preferring one with an identical plan tree.

    A same-plan baseline makes the comparison paired: planning replayed from the
    cache, so the writing side is the only variable. When no earlier run shares the
    plan tree, the newest scorable earlier run is returned as an unpaired baseline.
    ``probes`` are measured on every candidate baseline, so both sides of a
    comparison carry the same probe rows.
    """
    run_dir = Path(candidate.run_dir)
    siblings = sorted(
        (path for path in run_dir.parent.iterdir() if path.is_dir() and path.name < run_dir.name),
        key=lambda path: path.name,
        reverse=True,
    )[:scan]
    fallback: RunScorecard | None = None
    for sibling in siblings:
        try:
            card = score_run(sibling, probes=probes)
        except (OSError, ValueError):
            continue
        if card.plan_fingerprint == candidate.plan_fingerprint:
            return card
        if fallback is None:
            fallback = card
    return fallback
