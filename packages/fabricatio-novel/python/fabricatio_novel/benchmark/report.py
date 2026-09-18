"""Render the benchmark reports through the shared handlebars store.

The scorer measures, and the models carry the printed form of every number a
report shows (the ``*_display`` computed fields).  The scorecard and the
comparison each bind one model dump to one template, so their labels, columns
and line breaks live in ``templates/built-in/bench_*.hbs`` and are rewritten
without touching Python.  The tables themselves come from the models, because
handlebars can neither measure a column nor pad a cell — the templates print
``{{table.display}}`` as-is.  The board is one table and nothing else, so it has
no template at all: ``Board`` renders it and this module returns that string.
"""

from collections.abc import Sequence

from fabricatio_core.rust import TEMPLATE_MANAGER

from fabricatio_novel.benchmark.models import Board, Comparison, ProseScan, RunScorecard, Scan
from fabricatio_novel.config import novel_config


def render_scorecard(card: RunScorecard) -> str:
    """Render one run's scorecard."""
    return TEMPLATE_MANAGER.render_template(novel_config.bench_scorecard_template, card.model_dump(mode="json"))


def render_comparison(comparison: Comparison) -> str:
    """Render a candidate run against its baseline, one table row per metric."""
    return TEMPLATE_MANAGER.render_template(novel_config.bench_comparison_template, comparison.model_dump(mode="json"))


def render_board(cards: Sequence[RunScorecard]) -> str:
    """Render the runs as one table, in the order they are given in."""
    return Board.of(cards).display


def render_scan(scans: Sequence[ProseScan]) -> str:
    """Render scanned files as one table, then the gated hits and mixed names file by file."""
    lines = [Scan.of(scans).display]
    for scan in scans:
        if scan.probes.gated:
            lines.append(
                f"gated {scan.path}: "
                + ", ".join(f"{term}x{count}" for term, count in sorted(scan.probes.gated.items()))
            )
        for group, counts in scan.probes.aliases.items():
            mixed = ", ".join(f"{term}x{count}" for term, count in counts.items())
            lines.append(f"mixed {scan.path}: one object named {group} — {mixed}")
    return "\n".join(lines)
