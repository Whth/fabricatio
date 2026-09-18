"""Deterministic quality benchmark for novel runs.

Scoring a run is artifact-only: the stage snapshots, chapter exports and EPUB a
run already persisted are enough, so a scorecard costs no LLM calls and can be
recomputed at any time. The plan tree is the ground truth — a scene may use what
its own plan and the prose before it license, and nothing else — which makes the
same metrics meaningful for every novel without a hand-written rubric.

Typical use: score a run, compare it against the newest comparable earlier run,
and read the board to spot the run that introduced a regression.
"""

from fabricatio_novel.benchmark.compare import compare, find_baseline, sign_test_p
from fabricatio_novel.benchmark.enums import Gate, Metric, Verdict
from fabricatio_novel.benchmark.models import Comparison, GateFailure, MetricDelta, ProseScan, RunScorecard
from fabricatio_novel.benchmark.probes import TermProbes
from fabricatio_novel.benchmark.report import render_board, render_comparison, render_scan, render_scorecard
from fabricatio_novel.benchmark.scorecard import score_run

__all__ = [
    "Comparison",
    "Gate",
    "GateFailure",
    "Metric",
    "MetricDelta",
    "ProseScan",
    "RunScorecard",
    "TermProbes",
    "Verdict",
    "compare",
    "find_baseline",
    "render_board",
    "render_comparison",
    "render_scan",
    "render_scorecard",
    "score_run",
    "sign_test_p",
]
